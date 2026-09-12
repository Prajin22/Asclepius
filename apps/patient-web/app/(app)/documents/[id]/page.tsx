"use client";

import { useApi, useQuery } from "@carebridge/api-client/react";
import { useI18n } from "@carebridge/i18n";
import { languageInfo } from "@carebridge/shared-types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DocumentViewer,
  ErrorState,
  PageHeader,
  ProvenanceChip,
  SkeletonCard,
  buttonClasses,
  formatBytes,
} from "@carebridge/ui";
import { Eye, EyeSlash } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DocumentReadingPanel } from "@/components/DocumentReadingPanel";
import { ArrowLeftIcon } from "@/components/icons";

const STATUS_TONE = {
  uploaded: "neutral",
  processing: "info",
  processed: "success",
  failed: "danger",
} as const;

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useApi();
  const { t, formatDateTime } = useI18n();
  const q = useQuery((a) => a.patient.document(id), [id]);
  const profile = useQuery((a) => a.patient.profile());
  // Stored reading only; nothing is processed until the patient asks.
  const reading = useQuery((a) => a.documents.extraction(id), [id]);
  const [showOriginal, setShowOriginal] = useState(false);

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
  if (!q.data) return <SkeletonCard />;
  const doc = q.data;

  return (
    <>
      <PageHeader
        eyebrow={back}
        title={doc.title || doc.file_name}
        description={t("documents.uploadedOn", { date: formatDateTime(doc.uploaded_at) })}
        actions={
          <Button variant="secondary" onClick={() => setShowOriginal((v) => !v)} aria-expanded={showOriginal}>
            {showOriginal ? <EyeSlash size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
            {showOriginal ? t("actions.close") : t("document.preview")}
          </Button>
        }
      />

      {/* Facts about the file itself, as chips rather than a table. */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <ProvenanceChip kind="document" label={t(`documentType.${doc.document_type}`)} />
        <Badge tone={STATUS_TONE[doc.status]}>{t(`documentStatus.${doc.status}`)}</Badge>
        <Badge tone="neutral">{formatBytes(doc.size_bytes, t)}</Badge>
        {doc.source_language ? (
          <Badge tone="neutral">{languageInfo(doc.source_language)?.nativeName ?? doc.source_language}</Badge>
        ) : null}
        <span className="truncate text-small text-subtle">{doc.file_name}</span>
      </div>

      {showOriginal ? (
        <Card className="mb-5" aria-labelledby="original-heading">
          <CardHeader id="original-heading" title={t("document.preview")} description={t("docAi.originalStays")} />
          <DocumentViewer
            load={() => api.patient.documentFile(doc.id)}
            mimeType={doc.mime_type}
            fileName={doc.file_name}
          />
        </Card>
      ) : null}

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
    </>
  );
}
