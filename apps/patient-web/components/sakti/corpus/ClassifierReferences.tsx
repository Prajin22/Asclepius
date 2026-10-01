"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { errorMessage, useT } from "@carebridge/i18n";
import type { ProvisionVersionDetail } from "@carebridge/shared-types";
import { Alert, Button, Field, Select, SkeletonCard } from "@carebridge/ui";
import { useState } from "react";
import { ReferenceList } from "@/components/sakti/classify/ReferenceList";

/**
 * On an approved provision version: link it to a classifier reference slot of
 * the same lane. The server refuses anything unapproved or from the other lane.
 */
export function ClassifierReferenceLinker({ version }: { version: ProvisionVersionDetail }) {
  const api = useApi();
  const t = useT();
  const tree = useQuery((a) => a.classifier.tree());
  const [slotId, setSlotId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState(false);

  if (!tree.data) return <SkeletonCard />;
  const slots = tree.data.slots.filter((s) => s.lane === version.lane);
  const supported = tree.data.slots.filter((s) => s.provision?.provision_version_id === version.id);
  const chosen = slotId || slots[0]?.id || "";

  async function link() {
    if (!tree.data || !chosen) return;
    setBusy(true);
    setError(null);
    setNotice(false);
    try {
      await api.corpus.linkClassifierReference(tree.data.version, chosen, version.id);
      setNotice(true);
      tree.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-muted">{t("corpus.classifier.help")}</p>
      <div>
        <p className="text-small font-semibold text-muted">{t("corpus.classifier.current")}</p>
        {supported.length ? (
          <div className="mt-2">
            <ReferenceList slots={supported} />
          </div>
        ) : (
          <p className="mt-1 text-muted">{t("corpus.classifier.none")}</p>
        )}
      </div>
      {slots.length ? (
        <div className="flex flex-col gap-3">
          <Field label={t("corpus.classifier.slot")}>
            {(p) => (
              <Select {...p} value={chosen} onChange={(e) => setSlotId(e.target.value)}>
                {slots.map((slot) => (
                  <option key={slot.id} value={slot.id}>
                    {t(slot.describes_key)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {notice ? <Alert tone="success">{t("corpus.classifier.linked")}</Alert> : null}
          {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
          <div>
            <Button variant="secondary" onClick={link} disabled={busy}>
              {busy ? t("corpus.classifier.linking") : t("corpus.classifier.link")}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Every classifier reference slot and its status, for the corpus overview. */
export function ClassifierReferenceStatus() {
  const t = useT();
  const tree = useQuery((a) => a.classifier.tree());
  if (!tree.data) return <SkeletonCard />;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-small text-muted">{t("corpus.classifier.listHelp")}</p>
      <ReferenceList slots={tree.data.slots} />
    </div>
  );
}
