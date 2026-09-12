"use client";

import { useT } from "@carebridge/i18n";
import { useEffect, useState } from "react";
import { buttonClasses } from "./Button";
import { ErrorState, LoadingState } from "./Feedback";

/**
 * Fetches a document through the authenticated API and previews it from a
 * blob: URL (so the bearer token never appears in a URL).
 */
export function DocumentViewer({
  load,
  mimeType,
  fileName,
}: {
  load: () => Promise<Blob>;
  mimeType: string;
  fileName: string;
}) {
  const t = useT();
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let revoked = false;
    let objectUrl: string | null = null;
    setError(null);
    setUrl(null);
    load()
      .then((blob) => {
        if (revoked) return;
        objectUrl = URL.createObjectURL(new Blob([blob], { type: mimeType }));
        setUrl(objectUrl);
      })
      .catch((e) => !revoked && setError(e));
    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mimeType, attempt]);

  if (error) return <ErrorState error={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (!url) return <LoadingState label={t("document.loadingFile")} />;

  const isImage = mimeType.startsWith("image/");
  const isPdf = mimeType === "application/pdf";
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-lg border border-line bg-sunken">
        {isImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={fileName} className="mx-auto max-h-[70vh] w-auto" />
        ) : isPdf ? (
          <iframe src={url} title={fileName} className="h-[70vh] w-full bg-white" />
        ) : (
          <p className="p-4 text-muted">{t("document.previewUnavailable")}</p>
        )}
      </div>
      <div>
        <a href={url} target="_blank" rel="noopener noreferrer" className={buttonClasses("secondary", "sm")}>
          {t("document.openNewTab")}
        </a>
      </div>
    </div>
  );
}
