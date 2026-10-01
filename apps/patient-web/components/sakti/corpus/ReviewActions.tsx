"use client";

import { errorMessage, useT } from "@carebridge/i18n";
import { Alert, Button, Checkbox, Field, TextArea } from "@carebridge/ui";
import { useState } from "react";
import { Checksum } from "./labels";

/**
 * Approve or reject one submitted record.
 *
 * The approval names the checksum the curator is looking at, so the server
 * approves exactly that and nothing that changed in between. Machine-read or
 * missing text must be acknowledged before the approve button does anything.
 */
export function ReviewActions({
  checksum,
  needsAcknowledgment,
  blocked,
  onApprove,
  onReject,
}: {
  checksum: string;
  needsAcknowledgment: boolean;
  /** Why approval is not possible yet, if it is not. */
  blocked?: string;
  onApprove: (acknowledged: boolean) => Promise<unknown>;
  onReject: (reason: string) => Promise<unknown>;
}) {
  const t = useT();
  const [acknowledged, setAcknowledged] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function run(kind: "approve" | "reject") {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "approve") await onApprove(acknowledged);
      else await onReject(reason.trim());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-muted">
        {t("corpus.review.checksumNote")}
        <Checksum value={checksum} className="mt-1 block" />
      </p>
      {blocked ? <Alert tone="warning">{blocked}</Alert> : null}
      {needsAcknowledgment && !blocked ? (
        <Checkbox label={t("corpus.review.acknowledge")} checked={acknowledged} onChange={setAcknowledged} />
      ) : null}
      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      {rejecting ? (
        <div className="flex flex-col gap-3">
          <Field label={t("corpus.review.reason")}>
            {(p) => <TextArea {...p} rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />}
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button variant="danger" disabled={!reason.trim() || busy !== null} onClick={() => run("reject")}>
              {busy === "reject" ? t("corpus.review.rejecting") : t("corpus.review.confirmReject")}
            </Button>
            <Button variant="ghost" onClick={() => setRejecting(false)} disabled={busy !== null}>
              {t("corpus.review.cancel")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => run("approve")}
            disabled={busy !== null || Boolean(blocked) || (needsAcknowledgment && !acknowledged)}
          >
            {busy === "approve" ? t("corpus.review.approving") : t("corpus.review.approve")}
          </Button>
          <Button variant="secondary" onClick={() => setRejecting(true)} disabled={busy !== null}>
            {t("corpus.review.reject")}
          </Button>
        </div>
      )}
    </div>
  );
}
