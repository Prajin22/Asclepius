"use client";

import { useI18n } from "@carebridge/i18n";
import type { Prescription } from "@carebridge/shared-types";
import { Stethoscope } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { cn } from "./cn";

/**
 * A doctor-authored prescription, written in ink.
 *
 * The inked header carries the author, their registration and the date, because
 * this is the one thing on screen that a person signed. Rendered exactly as
 * written: no AI rewording, merging or reordering, ever.
 */
export function PrescriptionCard({
  prescription,
  footer,
  className,
}: {
  prescription: Prescription;
  footer?: ReactNode;
  className?: string;
}) {
  const { t, formatDate } = useI18n();
  const { authored_by: doctor } = prescription;
  return (
    <article className={cn("overflow-hidden rounded-md border border-ink bg-surface", className)}>
      <header className="on-dark flex flex-wrap items-start justify-between gap-3 bg-ink px-4 py-3.5 text-white sm:px-5">
        <div className="min-w-0">
          <p className="text-subheading">{doctor.name}</p>
          <p className="text-small text-white/75">
            {doctor.specialization} · {t("prescription.registration", { id: doctor.registration_identifier })}
          </p>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <span className="inline-flex items-center gap-1.5 rounded-sm border border-white/30 bg-white/10 px-2 py-0.5 text-caption font-semibold">
            <Stethoscope size={13} weight="bold" aria-hidden />
            {t("prescription.doctorAuthored")}
          </span>
          <time dateTime={prescription.created_at} className="text-small text-white/75">
            {t("prescription.issuedOn", { date: formatDate(prescription.created_at) })}
          </time>
        </div>
      </header>
      <ol className="divide-y divide-line">
        {prescription.items.map((item) => (
          <li key={item.position} className="px-4 py-4 sm:px-5">
            <p className="flex gap-2 text-subheading text-ink">
              <span className="tabular text-muted">{item.position}.</span>
              {item.medication}
            </p>
            <dl className="mt-2.5 grid grid-cols-1 gap-x-6 gap-y-2 text-small sm:grid-cols-3">
              {(["dosage", "frequency", "duration"] as const).map((field) => (
                <div key={field} className="flex gap-2 sm:block">
                  <dt className="text-label uppercase text-subtle">{t(`prescription.${field}`)}</dt>
                  <dd className="font-mono font-medium text-ink">{item[field]}</dd>
                </div>
              ))}
            </dl>
            {item.instructions ? (
              <p className="mt-2.5 text-small">
                <span className="text-muted">{t("prescription.instructions")}: </span>
                {item.instructions}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
      {prescription.instructions ? (
        <div className="border-t border-line px-4 py-3.5 sm:px-5">
          <p className="text-label uppercase text-subtle">{t("prescription.generalAdvice")}</p>
          <p className="mt-1 whitespace-pre-line text-body">{prescription.instructions}</p>
        </div>
      ) : null}
      {footer ? <div className="border-t border-line px-4 py-3 text-small sm:px-5">{footer}</div> : null}
    </article>
  );
}
