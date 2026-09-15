import type { ReactNode } from "react";
import { cn } from "./cn";

/**
 * A sheet laid on the page. Surfaces carry meaning: `paper` is original material
 * (the patient's words, the uploaded file), `machine` is anything a machine
 * produced, `ink` is doctor-authored, `surface` is the product's own chrome.
 *
 * Sheets are flat and divided by creases; elevation is spent only on things that
 * genuinely sit above the page, such as a sheet on a phone or the document viewer.
 */
export type SurfaceTone = "surface" | "paper" | "machine" | "quiet" | "ink";

const tones: Record<SurfaceTone, string> = {
  surface: "border-line bg-surface",
  paper: "border-paper-line bg-paper",
  machine: "border-dashed border-ai-line bg-ai-soft",
  quiet: "border-line bg-sunken",
  ink: "border-ink bg-surface",
};

const paddings = {
  none: "",
  sm: "p-4",
  md: "p-5 sm:p-6",
  lg: "p-6 sm:p-8",
} as const;

export function Card({
  children,
  className,
  tone = "surface",
  padding = "md",
  as: Tag = "section",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  tone?: SurfaceTone;
  padding?: keyof typeof paddings;
  as?: "section" | "article" | "div" | "li";
  "aria-labelledby"?: string;
  "aria-label"?: string;
}) {
  return (
    <Tag className={cn("rounded-md border", tones[tone], paddings[padding], className)} {...rest}>
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  description,
  action,
  id,
  level = 2,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  id?: string;
  level?: 2 | 3;
  className?: string;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    // No wrap: an action stays on the title's line instead of dropping under it with an odd indent.
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <Heading id={id} className="text-heading text-ink">
          {title}
        </Heading>
        {description ? <p className="mt-1 text-small text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
