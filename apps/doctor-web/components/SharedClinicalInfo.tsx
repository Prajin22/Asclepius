"use client";

import { useI18n } from "@carebridge/i18n";
import type { CaseView, MedicalRecord, RecordType, SharedConsultation } from "@carebridge/shared-types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DocumentViewer,
  LanguageTag,
  PrescriptionCard,
  SourceBadge,
  formatBytes,
} from "@carebridge/ui";
import { useState } from "react";
import { AIInsight } from "@/components/AIInsight";
import { DocumentInsight } from "@/components/DocumentInsight";
import { languageLabel } from "@/lib/format";

const HISTORY_ORDER: RecordType[] = ["condition", "allergy", "medication", "history_note", "family_history"];

function NotShared() {
  const { t } = useI18n();
  return <p className="text-sm italic text-subtle">{t("case.notShared")}</p>;
}

function HistoryRow({ r }: { r: MedicalRecord }) {
  const { formatDate, t } = useI18n();
  return (
    <li className="grid gap-1 py-2.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
      <span className="text-sm font-medium text-muted">{t(`recordType.${r.type}`)}</span>
      <div className="min-w-0">
        <p className="font-semibold">
          {r.title ?? t(`recordType.${r.type}`)}
          {r.status === "resolved" ? (
            <Badge className="ml-2 align-middle">{t("recordStatus.resolved")}</Badge>
          ) : null}
        </p>
        {r.content ? (
          <p lang={r.source_language} className="whitespace-pre-line text-sm">
            {r.content}
          </p>
        ) : null}
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
          <SourceBadge source={r.source} />
          <LanguageTag code={r.source_language} />
          <span>{formatDate(r.created_at)}</span>
        </div>
      </div>
    </li>
  );
}

function OpinionCard({ c, independent }: { c: SharedConsultation; independent: boolean }) {
  const { t, formatDate } = useI18n();
  return (
    <article className="rounded-lg border border-line p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{t("case.doctorOf", { name: c.doctor.name, specialization: c.doctor.specialization })}</p>
          <p className="text-sm text-muted">
            {formatDate(c.started_at ?? c.created_at)}
            {c.completed_at ? ` – ${formatDate(c.completed_at)}` : ""} · {t(`status.${c.status}`)}
          </p>
        </div>
        {independent ? <Badge tone="info">{t("source.doctor")}</Badge> : null}
      </header>
      {c.doctor_assessment ? (
        <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{c.doctor_assessment}</p>
      ) : (
        <p className="mt-2 text-sm text-subtle">{t("case.noNotes")}</p>
      )}
    </article>
  );
}

/**
 * Everything the patient shared for this consultation, with source
 * attribution on every item. Other doctors' opinions stay separate and
 * attributed — they are never merged with, or ranked against, this doctor's.
 */
export function SharedClinicalInfo({
  view,
  loadDocument,
  loadPage,
}: {
  view: CaseView;
  loadDocument: (documentId: string) => Promise<Blob>;
  loadPage?: (documentId: string, page: number) => Promise<Blob>;
}) {
  const { t, formatDate, formatDateTime } = useI18n();
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const shared = new Set(view.shared_categories);
  const insightFor = new Map(view.ai_insights.map((i) => [i.record_id, i]));
  const readingFor = new Map(view.document_insights.map((i) => [i.document_id, i]));
  const history = [...view.medical_history].sort(
    (a, b) => HISTORY_ORDER.indexOf(a.type) - HISTORY_ORDER.indexOf(b.type),
  );

  return (
    <div className="flex flex-col gap-5">
      <Card className="border-l-4 border-l-brand">
        <CardHeader title={t("case.currentProblem")} description={t("case.patientWords")} />
        {view.current_problems.length === 0 ? (
          <NotShared />
        ) : (
          <div className="flex flex-col gap-4">
            {view.current_problems.map((p) => (
              <figure key={p.id}>
                <blockquote lang={p.source_language} className="whitespace-pre-line text-lg leading-relaxed text-ink">
                  {p.content}
                </blockquote>
                <figcaption className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                  <SourceBadge source={p.source} />
                  <span>{t("language.writtenIn", { language: languageLabel(p.source_language) })}</span>
                  <span>· {formatDateTime(p.created_at)}</span>
                </figcaption>
                {insightFor.has(p.id) ? <AIInsight insight={insightFor.get(p.id)!} /> : null}
              </figure>
            ))}
          </div>
        )}
        {view.request_message ? (
          <div className="mt-4 rounded-lg bg-sunken px-4 py-3">
            <p className="text-sm font-semibold text-muted">{t("case.patientNote")}</p>
            <p lang={view.request_language ?? undefined} className="mt-0.5 whitespace-pre-line">
              {view.request_message}
            </p>
          </div>
        ) : null}
      </Card>

      <Card>
        <CardHeader title={t("case.history")} />
        {history.length === 0 ? <NotShared /> : <ul className="divide-y divide-line">{history.map((r) => <HistoryRow key={r.id} r={r} />)}</ul>}
      </Card>

      <Card>
        <CardHeader title={t("case.documents")} />
        {view.documents.length === 0 ? (
          <NotShared />
        ) : (
          <ul className="flex flex-col gap-2">
            {view.documents.map((d) => (
              <li key={d.id} className="rounded-lg border border-line">
                <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{d.title || d.file_name}</p>
                    <p className="text-sm text-muted">
                      {t(`documentType.${d.document_type}`)} · {formatDate(d.uploaded_at)} · {formatBytes(d.size_bytes, t)}
                      {d.source_language ? ` · ${languageLabel(d.source_language)}` : ""}
                    </p>
                  </div>
                  <Button
                    variant={openDoc === d.id ? "ghost" : "secondary"}
                    size="sm"
                    aria-expanded={openDoc === d.id}
                    onClick={() => setOpenDoc(openDoc === d.id ? null : d.id)}
                  >
                    {openDoc === d.id ? t("actions.close") : t("actions.view")}
                  </Button>
                </div>
                {openDoc === d.id ? (
                  <div className="border-t border-line p-3">
                    <DocumentViewer load={() => loadDocument(d.id)} mimeType={d.mime_type} fileName={d.file_name} />
                  </div>
                ) : null}
                {readingFor.has(d.id) ? (
                  <div className="px-3.5 pb-3">
                    <DocumentInsight
                      insight={readingFor.get(d.id)!}
                      loadPage={loadPage ? (page) => loadPage(d.id, page) : undefined}
                    />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {shared.has("previous_consultations") || view.shared_consultations.length > 0 ? (
        <Card>
          <CardHeader title={t("case.sharedConsultations")} description={t("case.independentOpinion")} />
          <div className="flex flex-col gap-3">
            {view.shared_consultations.map((c) => (
              <OpinionCard key={c.id} c={c} independent />
            ))}
          </div>
        </Card>
      ) : null}

      {view.shared_prescriptions.length > 0 ? (
        <Card>
          <CardHeader title={t("case.sharedPrescriptions")} description={t("case.independentOpinion")} />
          <div className="flex flex-col gap-3">
            {view.shared_prescriptions.map((rx) => (
              <PrescriptionCard key={rx.id} prescription={rx} />
            ))}
          </div>
        </Card>
      ) : null}

      {view.own_previous_consultations.length > 0 ? (
        <Card>
          <CardHeader title={t("case.ownPrevious")} />
          <div className="flex flex-col gap-3">
            {view.own_previous_consultations.map((c) => (
              <OpinionCard key={c.id} c={c} independent={false} />
            ))}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
