"use client";

import { useT } from "@carebridge/i18n";
import { useEffect, useState } from "react";
import { cn } from "./cn";
import { ErrorState, LoadingState } from "./Feedback";

/** A region of the page: [x0, y0, x1, y1] as fractions of width and height, origin top-left. */
export type RegionBox = [number, number, number, number];

export interface PageRegion {
  id: string;
  bbox: RegionBox;
  active?: boolean;
}

// Breathing room so an outline does not sit on top of the letters it marks.
const PAD = 0.004;

/**
 * One page of the original document with evidence outlined on top.
 *
 * The outlines are an overlay; the page image itself is the untouched original,
 * fetched through the authenticated API as a blob (so no token appears in a URL).
 * A region drawn by the machine is dashed like any other crease; the one the
 * reader asked about takes the gold mark.
 */
export function PageImage({
  load,
  page,
  regions = [],
  className,
}: {
  load: () => Promise<Blob>;
  page: number;
  regions?: PageRegion[];
  className?: string;
}) {
  const t = useT();
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setError(null);
    setUrl(null);
    load()
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(new Blob([blob], { type: "image/png" }));
        setUrl(objectUrl);
      })
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, attempt]);

  if (error) return <ErrorState error={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (!url) return <LoadingState label={t("document.loadingFile")} />;

  return (
    <div className={cn("relative overflow-hidden rounded-md border border-paper-line bg-white", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt={t("reading.pageImageAlt", { page })} className="block h-auto w-full" />
      {regions.map((region) => {
        const [x0, y0, x1, y1] = region.bbox;
        const left = Math.max(0, x0 - PAD);
        const top = Math.max(0, y0 - PAD);
        const right = Math.min(1, x1 + PAD);
        const bottom = Math.min(1, y1 + PAD);
        return (
          <span
            key={region.id}
            aria-hidden
            data-testid="evidence-region"
            data-active={region.active ? "true" : "false"}
            className={cn(
              "pointer-events-none absolute rounded-sm transition-colors",
              region.active
                ? "border-2 border-mark-ink bg-mark/30"
                : "border border-dashed border-ai-line bg-ai/[0.06]",
            )}
            style={{
              left: `${left * 100}%`,
              top: `${top * 100}%`,
              width: `${(right - left) * 100}%`,
              height: `${(bottom - top) * 100}%`,
            }}
          />
        );
      })}
    </div>
  );
}
