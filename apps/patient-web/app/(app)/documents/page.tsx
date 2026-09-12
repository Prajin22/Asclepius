"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import {
  Badge,
  Card,
  CardHeader,
  ErrorState,
  LanguageTag,
  PageHeader,
  ProvenanceChip,
  SkeletonCard,
  formatBytes,
} from "@carebridge/ui";
import { ArrowRight, FilePlus } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { UploadForm } from "@/components/UploadForm";

const STATUS_TONE = {
  uploaded: "neutral",
  processing: "info",
  processed: "success",
  failed: "danger",
} as const;

export default function DocumentsPage() {
  const api = useApi();
  const { t, formatDate } = useI18n();
  const q = useQuery((a) => a.patient.documents());

  return (
    <>
      <PageHeader title={t("documents.title")} description={t("documents.subtitle")} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div>
          <UploadForm upload={(input) => api.patient.uploadDocument(input)} onUploaded={() => void q.reload()} />
        </div>

        <Card aria-labelledby="your-documents-heading">
          <CardHeader
            id="your-documents-heading"
            title={t("documents.yours")}
            description={t("documents.processingNotice")}
          />
          {q.error && !q.data ? (
            <ErrorState error={q.error} onRetry={q.reload} />
          ) : !q.data ? (
            <SkeletonCard className="border-0 p-0" />
          ) : q.data.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line-strong bg-sunken/60 px-4 py-10 text-center">
              <FilePlus size={26} aria-hidden className="mx-auto text-subtle" />
              <p className="mt-2 font-medium text-ink">{t("documents.empty")}</p>
              <p className="mt-1 text-small text-muted">{t("documents.fileHint")}</p>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {q.data.map((doc) => (
                <li key={doc.id}>
                  <Link
                    href={`/documents/${doc.id}`}
                    className="group flex items-start gap-3 rounded-lg border border-line px-3.5 py-3 transition-colors duration-150 hover:border-brand/40 hover:bg-brand-tint"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-ink">{doc.title || doc.file_name}</span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-2">
                        <ProvenanceChip kind="document" label={t(`documentType.${doc.document_type}`)} />
                        <Badge tone={STATUS_TONE[doc.status]}>{t(`documentStatus.${doc.status}`)}</Badge>
                        <LanguageTag code={doc.source_language} />
                      </span>
                      <span className="mt-1.5 block text-small text-muted">
                        {t("documents.uploadedOn", { date: formatDate(doc.uploaded_at) })} ·{" "}
                        {formatBytes(doc.size_bytes, t)}
                      </span>
                    </span>
                    <ArrowRight
                      size={18}
                      aria-hidden
                      className="mt-1 shrink-0 text-subtle transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-brand"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
