"use client";

import { useI18n } from "@carebridge/i18n";
import type { CorpusDiff, DiffBlock } from "@carebridge/shared-types";
import { cn } from "@carebridge/ui";
import type { ReactNode } from "react";

/**
 * A deterministic diff, drawn as the server computed it (difflib). It shows
 * which characters differ and nothing else — no summary of what a change means.
 * Removed and added text are marked by a sign and a label as well as colour.
 */
export function DiffView({ diff, noBaseline }: { diff: CorpusDiff; noBaseline: string }) {
  const { t, formatDate } = useI18n();
  const { stats } = diff;
  const identical = stats.added + stats.removed + stats.changed === 0;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-small text-muted">
        {diff.baseline
          ? t("corpus.diff.against", {
              label: diff.baseline.label,
              date: diff.baseline.approved_at ? formatDate(diff.baseline.approved_at) : "—",
            })
          : noBaseline}
      </p>
      <p className="text-small font-semibold text-ink">{identical ? t("corpus.diff.identical") : t("corpus.diff.stats", stats)}</p>
      <div className="overflow-x-auto rounded-md border border-line bg-surface">
        <ol className="min-w-full font-mono text-small leading-relaxed">
          {diff.blocks.map((block, index) => (
            <Block key={index} block={block} />
          ))}
        </ol>
      </div>
    </div>
  );
}

function Line({ sign, label, tone, children }: { sign: string; label?: string; tone?: "add" | "del"; children: ReactNode }) {
  return (
    <li
      className={cn(
        "grid grid-cols-[1.75rem_minmax(0,1fr)] whitespace-pre-wrap break-words px-2 py-0.5",
        tone === "add" && "bg-success-soft text-ink",
        tone === "del" && "bg-danger-soft text-ink",
      )}
    >
      <span aria-hidden className="select-none text-subtle">
        {sign}
      </span>
      <span>
        {label ? <span className="sr-only">{label}: </span> : null}
        {children}
      </span>
    </li>
  );
}

function Block({ block }: { block: DiffBlock }) {
  const { t } = useI18n();
  if (block.op === "equal") {
    return (
      <>
        {(block.lines ?? []).map((line, i) => (
          <Line key={`h${i}`} sign=" ">
            {line}
          </Line>
        ))}
        {block.skipped ? (
          <li className="border-y border-dashed border-line bg-sunken px-3 py-1 font-sans text-caption text-muted">
            {t("corpus.diff.unchanged", { count: block.skipped })}
          </li>
        ) : null}
        {(block.tail ?? []).map((line, i) => (
          <Line key={`t${i}`} sign=" ">
            {line}
          </Line>
        ))}
      </>
    );
  }
  if (block.op === "replace" && block.words) {
    return (
      <li className="border-y border-line px-2 py-1">
        <p className="font-sans text-caption font-semibold text-muted">{t("corpus.diff.changed")}</p>
        <p className="whitespace-pre-wrap break-words">
          {block.words.map((part, i) =>
            part.op === "equal" ? (
              <span key={i}>{part.text}</span>
            ) : part.op === "delete" ? (
              <del key={i} className="bg-danger-soft text-ink decoration-danger">
                <span className="sr-only">{t("corpus.diff.removed")}: </span>
                {part.text}
              </del>
            ) : (
              <ins key={i} className="bg-success-soft text-ink no-underline">
                <span className="sr-only">{t("corpus.diff.added")}: </span>
                {part.text}
              </ins>
            ),
          )}
        </p>
      </li>
    );
  }
  return (
    <>
      {(block.old ?? []).map((line, i) => (
        <Line key={`o${i}`} sign="−" label={t("corpus.diff.removed")} tone="del">
          {line}
        </Line>
      ))}
      {(block.new ?? []).map((line, i) => (
        <Line key={`n${i}`} sign="+" label={t("corpus.diff.added")} tone="add">
          {line}
        </Line>
      ))}
    </>
  );
}
