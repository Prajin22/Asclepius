"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { languageInfo } from "@carebridge/shared-types";
import { Card, CardHeader, DocumentViewer, ErrorState, LoadingState, PageHeader, formatBytes } from "@carebridge/ui";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DocumentReadingPanel } from "@/components/DocumentReadingPanel";
import { ArrowLeftIcon } from "@/components/icons";

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.patient.document(id), [id]);
  const profile = useQuery((a) => a.patient.profile());
  // Stored reading only; nothing is processed until the patient asks.
  const reading = useQuery((a) => a.documents.extraction(id), [id]);

  const back = (
    <Link href="/documents" className="inline-flex items-center gap-1.5 font-medium text-brand hover:underline">
      <ArrowLeftIcon />
      {t("documents.back")}
    </Link>
  );

  if (q.error && !q.data) {
    return (
      <>
        {back}
        <ErrorState error={q.error} onRetry={q.reload} />
      </>
    );
  }
  if (!q.data) return <LoadingState />;
  const doc = q.data;

  const rows: [string, string][] = [
    [t("documents.type"), t(`documentType.${doc.document_type}`)],
    [t("documents.fileName"), doc.file_name],
    [t("documents.fileType"), doc.mime_type],
    [t("documents.fileSize"), formatBytes(doc.size_bytes, t)],
    [t("documents.language"), languageInfo(doc.source_language)?.nativeName ?? t("documents.notSpecified")],
    [t("documents.status"), t(`documentStatus.${doc.status}`)],
  ];

  return (
    <>
      <PageHeader
        eyebrow={back}
        title={doc.title || doc.file_name}
        description={t("documents.uploadedOn", { date: formatDateTime(doc.uploaded_at) })}
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title={t("document.preview")} />
          <DocumentViewer load={() => api.patient.documentFile(doc.id)} mimeType={doc.mime_type} fileName={doc.file_name} />
        </Card>
        <Card>
          <CardHeader title={t("documents.details")} />
          <dl className="flex flex-col gap-3">
            {rows.map(([label, value]) => (
              <div key={label}>
                <dt className="text-sm text-muted">{label}</dt>
                <dd className="break-words font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
      <div className="mt-5">
        <DocumentReadingPanel
          hasConsent={profile.data?.ai_processing_consent ?? false}
          result={reading.data ?? null}
          onGrantConsent={async () => {
            await api.ai.setConsent(true);
            await profile.reload();
          }}
          onProcess={async () => {
            const processed = await api.documents.process(doc.id);
            void q.reload(); // document status changes to processed / failed
            return processed;
          }}
          onReviewFact={(factId, action) => api.ai.reviewFact(factId, action)}
          loadPage={(page) => api.documents.pageImage(doc.id, page)}
        />
      </div>
    </>
  );
}
