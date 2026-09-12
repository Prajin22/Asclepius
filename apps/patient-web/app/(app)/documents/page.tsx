"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { Badge, Card, CardHeader, EmptyState, ErrorState, LanguageTag, LoadingState, PageHeader, formatBytes } from "@carebridge/ui";
import Link from "next/link";
import { FileIcon } from "@/components/icons";
import { UploadForm } from "@/components/UploadForm";

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
        <Card>
          <CardHeader title={t("documents.yours")} description={t("documents.processingNotice")} />
          {q.error && !q.data ? (
            <ErrorState error={q.error} onRetry={q.reload} />
          ) : !q.data ? (
            <LoadingState />
          ) : q.data.length === 0 ? (
            <EmptyState>{t("documents.empty")}</EmptyState>
          ) : (
            <ul className="flex flex-col gap-2">
              {q.data.map((doc) => (
                <li key={doc.id}>
                  <Link
                    href={`/documents/${doc.id}`}
                    className="flex items-start gap-3 rounded-lg border border-line px-3.5 py-3 hover:border-brand/40 hover:bg-sunken"
                  >
                    <span className="mt-0.5 rounded-md bg-brand-soft p-1.5 text-brand">
                      <FileIcon />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{doc.title || doc.file_name}</span>
                      <span className="block text-sm text-muted">
                        {t(`documentType.${doc.document_type}`)} · {t("documents.uploadedOn", { date: formatDate(doc.uploaded_at) })}{" "}
                        · {formatBytes(doc.size_bytes, t)}
                      </span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-2">
                        <Badge tone="neutral">{t(`documentStatus.${doc.status}`)}</Badge>
                        <LanguageTag code={doc.source_language} />
                      </span>
                    </span>
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
