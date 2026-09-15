"use client";

import type { ReactNode } from "react";
import { cn } from "./cn";

/**
 * The numbered margin column.
 *
 * Any real sequence in Asclepius is a set of folds: describe, organise, confirm,
 * share, decide. On a wide screen the steps run down the margin with the gold dot
 * on the current one; on a phone the same track becomes one line, "Step 2 of 5",
 * with a crease that fills as you go. The numbers are information, not decoration:
 * they only appear where the order actually matters.
 */
export interface FoldStep {
  key: string;
  label: string;
}

export function FoldTrack({
  steps,
  current,
  label,
  className,
  inline = false,
}: {
  steps: FoldStep[];
  current: string;
  /** Names the sequence for assistive technology, e.g. "Reading this document". */
  label: string;
  className?: string;
  /** Keeps the compact one-line form at every width, for a track inside a panel. */
  inline?: boolean;
}) {
  const index = Math.max(
    0,
    steps.findIndex((s) => s.key === current),
  );
  const step = steps[index];

  return (
    <div className={className}>
      {/* Phone: one line, and a crease that shows how far along you are. */}
      <div className={inline ? undefined : "lg:hidden"}>
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="tabular text-label uppercase text-subtle">
            {label} · {index + 1}/{steps.length}
          </span>
          <span className="text-small font-semibold text-ink">{step?.label}</span>
        </p>
        <ol aria-label={label} className="mt-2 flex gap-1">
          {steps.map((s, i) => (
            <li
              key={s.key}
              aria-current={s.key === current ? "step" : undefined}
              className={cn(
                "h-0.5 flex-1 rounded-sm",
                i < index && "bg-ink",
                i === index && "bg-mark",
                i > index && "bg-line",
              )}
            >
              <span className="sr-only">{s.label}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Desktop: the margin column itself. */}
      <ol aria-label={label} className={cn("hidden lg:flex-col lg:gap-2.5", inline ? "" : "lg:flex")}>
        {steps.map((s, i) => {
          const done = i < index;
          const now = s.key === current;
          return (
            <li
              key={s.key}
              aria-current={now ? "step" : undefined}
              className="grid grid-cols-[1.75rem_minmax(0,1fr)] items-baseline gap-2"
            >
              <span
                className={cn("tabular text-step", now ? "text-mark-ink" : done ? "text-muted" : "text-subtle/70")}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className={cn("text-small", now ? "font-semibold text-ink" : "text-muted")}>
                {s.label}
                {now ? <Mark className="ml-1.5 align-middle" /> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/**
 * The gold dot: the one thing on this screen waiting for the person reading it.
 * It never carries meaning alone — a word always sits beside it.
 */
export function Mark({ className, label }: { className?: string; label?: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        aria-hidden
        className="inline-block size-2 shrink-0 rounded-full bg-mark ring-1 ring-mark-ink"
      />
      {label ? <span className="text-small font-semibold text-mark-ink">{label}</span> : null}
    </span>
  );
}

/**
 * The rule between panels. Solid is structure, drawn is machine-made, pressed is
 * confirmed by a person.
 */
export function Crease({ kind = "solid", className }: { kind?: "solid" | "drawn" | "pressed"; className?: string }) {
  return (
    <hr
      className={cn(
        kind === "solid" && "border-t border-line",
        kind === "drawn" && "border-t border-dashed border-ai-line",
        kind === "pressed" && "border-t border-ink",
        className,
      )}
    />
  );
}
