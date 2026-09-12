"use client";

import { useI18n } from "@carebridge/i18n";
import type { Prescription } from "@carebridge/shared-types";
import type { ReactNode } from "react";
import { Badge } from "./Badge";
import { cn } from "./cn";

/**
 * A doctor-authored prescription with attribution kept prominent.
 * Rendered exactly as written — no AI rewording, merging or reordering.
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
    <article className={cn("overflow-hidden rounded-xl border border-line bg-surface", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line bg-sunken px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t("prescription.title")}</p>
          <p className="mt-0.5 font-semibold text-ink">{doctor.name}</p>
          <p className="text-sm text-muted">
            {doctor.specialization} · {t("prescription.registration", { id: doctor.registration_identifier })}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Badge tone="brand">{t("prescription.doctorAuthored")}</Badge>
          <time dateTime={prescription.created_at} className="text-sm text-muted">
            {t("prescription.issuedOn", { date: formatDate(prescription.created_at) })}
          </time>
        </div>
      </header>
      <ol className="divide-y divide-line">
        {prescription.items.map((item) => (
          <li key={item.position} className="px-4 py-3.5 sm:px-5">
            <p className="font-semibold text-ink">
              <span className="mr-2 text-muted">{item.position}.</span>
              {item.medication}
            </p>
            <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
              {(["dosage", "frequency", "duration"] as const).map((field) => (
                <div key={field} className="flex gap-2 sm:block">
                  <dt className="text-muted">{t(`prescription.${field}`)}</dt>
                  <dd className="font-medium text-ink">{item[field]}</dd>
                </div>
              ))}
            </dl>
            {item.instructions ? (
              <p className="mt-2 text-sm">
                <span className="text-muted">{t("prescription.instructions")}: </span>
                {item.instructions}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
      {prescription.instructions ? (
        <div className="border-t border-line px-4 py-3 sm:px-5">
          <p className="text-sm font-semibold text-muted">{t("prescription.generalAdvice")}</p>
          <p className="mt-0.5 whitespace-pre-line">{prescription.instructions}</p>
        </div>
      ) : null}
      {footer ? <div className="border-t border-line px-4 py-3 text-sm sm:px-5">{footer}</div> : null}
    </article>
  );
}
