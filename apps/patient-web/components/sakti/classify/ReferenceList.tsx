"use client";

import { useT } from "@carebridge/i18n";
import type { ClassifierSlot, ReferenceStatus } from "@carebridge/shared-types";
import { Badge, type Tone } from "@carebridge/ui";

const TONE: Record<ReferenceStatus, Tone> = { verified: "success", unverified: "warning", corpus_required: "neutral" };
const NOTE: Record<ReferenceStatus, string> = {
  verified: "classifier.reference.verifiedNote",
  unverified: "classifier.reference.unverifiedNote",
  corpus_required: "classifier.reference.corpusRequiredNote",
};

/**
 * The legal pointers a result rests on, each with its status. Only a verified
 * pointer names a source, and then only by its approved, stored metadata — no
 * text is quoted, and nothing unverified is presented as a citation.
 */
export function ReferenceList({ slots }: { slots: ClassifierSlot[] }) {
  const t = useT();
  return (
    <ul className="flex flex-col divide-y divide-line">
      {slots.map((slot) => (
        <li key={slot.id} className="flex flex-col gap-1 py-2.5 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="text-ink">{t(slot.describes_key)}</span>
            <Badge tone={TONE[slot.status]}>{t(`classifier.reference.${slot.status}`)}</Badge>
          </div>
          {slot.status === "verified" && slot.provision ? (
            <p className="text-small text-ink">
              {t("classifier.reference.pointer", {
                instrument: slot.provision.instrument_title,
                locator: slot.provision.locator,
                version: slot.provision.version_number,
                source: slot.provision.source_title,
              })}
            </p>
          ) : null}
          <p className="text-caption text-muted">{t(NOTE[slot.status])}</p>
        </li>
      ))}
    </ul>
  );
}
