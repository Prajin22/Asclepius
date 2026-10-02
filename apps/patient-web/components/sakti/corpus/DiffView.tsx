"use client";

import { useI18n } from "@carebridge/i18n";
import type { CorpusDiff, DiffBlock } from "@carebridge/shared-types";
import { cn } from "@carebridge/ui";
import { Columns, Rows } from "@phosphor-icons/react/dist/ssr";
import { useState, useSyncExternalStore, type ReactNode } from "react";

const WIDE = "(min-width: 1024px)";

/** Whether the viewport is wide enough for two columns. False where there is no window (tests, prerender). */
function useWide(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const mq = window.matchMedia(WIDE);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(WIDE).matches : false),
    () => false,
  );
}

/**
 * A deterministic diff, drawn as the server computed it (difflib). It shows
 * which characters differ and nothing else — no summary of what a change means.
 * Removed and added text are marked by a sign and a label as well as colour.
 * On a wide screen the two texts can sit side by side; on a narrow one the
 * diff is always one column, removed above added.
 */
export function DiffView({ diff, noBaseline }: { diff: CorpusDiff; noBaseline: string }) {
  const { t, formatDate } = useI18n();
  const wide = useWide();
  const [mode, setMode] = useState<"split" | "inline">("split");
  const { stats } = diff;
  const identical = stats.added + stats.removed + stats.changed === 0;
  const split = wide && mode === "split" && diff.baseline !== null;
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-small font-semibold text-ink">{identical ? t("corpus.diff.identical") : t("corpus.diff.stats", stats)}</p>
        {wide && diff.baseline ? (
          <div role="group" aria-label={t("corpus.diff.layout")} className="inline-flex rounded-md border border-line-strong p-0.5">
            {(
              [
                ["split", Columns, "corpus.diff.split"],
                ["inline", Rows, "corpus.diff.inline"],
              ] as const
            ).map(([value, Glyph, key]) => (
              <button
                key={value}
                type="button"
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
                className={cn(
                  "inline-flex min-h-9 items-center gap-1.5 rounded-sm px-3 text-small font-semibold",
                  mode === value ? "bg-brand-soft text-brand-strong" : "text-muted hover:text-ink",
                )}
              >
                <Glyph size={16} aria-hidden />
                {t(key)}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="overflow-x-auto rounded-md border border-line bg-surface">
        {split ? (
          <SplitDiff blocks={diff.blocks} />
        ) : (
          <ol className="min-w-full font-mono text-small leading-relaxed">
            {diff.blocks.map((block, index) => (
              <Block key={index} block={block} />
            ))}
          </ol>
        )}
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
        {block.skipped ? <Fold count={block.skipped} /> : null}
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
          <Words words={block.words} show={["equal", "delete", "insert"]} />
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

function Fold({ count, cell = false }: { count: number; cell?: boolean }) {
  const { t } = useI18n();
  const className = "border-y border-dashed border-line bg-sunken px-3 py-1 font-sans text-caption text-muted";
  const text = t("corpus.diff.unchanged", { count });
  return cell ? (
    <td colSpan={2} className={className}>
      {text}
    </td>
  ) : (
    <li className={className}>{text}</li>
  );
}

function Words({ words, show }: { words: NonNullable<DiffBlock["words"]>; show: ("equal" | "delete" | "insert")[] }) {
  const { t } = useI18n();
  return (
    <>
      {words
        .filter((part) => show.includes(part.op))
        .map((part, i) =>
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
    </>
  );
}

/** The approved text on the left, the proposed text on the right, row against row. */
function SplitDiff({ blocks }: { blocks: DiffBlock[] }) {
  const { t } = useI18n();
  const rows: ReactNode[] = [];
  const cell = (content: ReactNode, tone?: "add" | "del", sign = " ", label?: string) => (
    <td
      className={cn(
        "w-1/2 border-line align-top whitespace-pre-wrap break-words px-2 py-0.5 first:border-r",
        tone === "add" && "bg-success-soft",
        tone === "del" && "bg-danger-soft",
      )}
    >
      <span className="grid grid-cols-[1.25rem_minmax(0,1fr)]">
        <span aria-hidden className="select-none text-subtle">
          {sign}
        </span>
        <span>
          {label && content !== null ? <span className="sr-only">{label}: </span> : null}
          {content}
        </span>
      </span>
    </td>
  );
  blocks.forEach((block, b) => {
    if (block.op === "equal") {
      const same = (line: string, key: string) => (
        <tr key={key}>
          {cell(line)}
          {cell(line)}
        </tr>
      );
      (block.lines ?? []).forEach((line, i) => rows.push(same(line, `${b}h${i}`)));
      if (block.skipped)
        rows.push(
          <tr key={`${b}f`}>
            <Fold count={block.skipped} cell />
          </tr>,
        );
      (block.tail ?? []).forEach((line, i) => rows.push(same(line, `${b}t${i}`)));
    } else if (block.op === "replace" && block.words) {
      rows.push(
        <tr key={`${b}w`}>
          {cell(<Words words={block.words} show={["equal", "delete"]} />, "del", "−")}
          {cell(<Words words={block.words} show={["equal", "insert"]} />, "add", "+")}
        </tr>,
      );
    } else {
      const old = block.old ?? [];
      const added = block.new ?? [];
      for (let i = 0; i < Math.max(old.length, added.length); i++) {
        rows.push(
          <tr key={`${b}p${i}`}>
            {i < old.length ? cell(old[i], "del", "−", t("corpus.diff.removed")) : cell(null)}
            {i < added.length ? cell(added[i], "add", "+", t("corpus.diff.added")) : cell(null)}
          </tr>,
        );
      }
    }
  });
  return (
    <table className="w-full table-fixed font-mono text-small leading-relaxed">
      <caption className="sr-only">{t("corpus.diff.title")}</caption>
      <thead className="border-b border-line bg-sunken font-sans">
        <tr>
          <th scope="col" className="border-r border-line px-3 py-2 text-left text-label uppercase text-muted">
            {t("corpus.diff.before")}
          </th>
          <th scope="col" className="px-3 py-2 text-left text-label uppercase text-muted">
            {t("corpus.diff.after")}
          </th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  );
}
