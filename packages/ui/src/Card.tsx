import type { ReactNode } from "react";
import { cn } from "./cn";

/**
 * Surfaces carry meaning: `paper` is original material (the patient's words, the
 * uploaded file), `machine` is anything a machine produced, `surface` is the
 * product's own chrome. See theme.css.
 */
export type SurfaceTone = "surface" | "paper" | "machine" | "quiet";

const tones: Record<SurfaceTone, string> = {
  surface: "border-line bg-surface",
  paper: "border-paper-line bg-paper",
  machine: "border-ai-line bg-ai-soft",
  quiet: "border-line bg-sunken",
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
    <Tag className={cn("rounded-xl border", tones[tone], paddings[padding], className)} {...rest}>
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  description,
  action,
  eyebrow,
  id,
  level = 2,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  /** Small label above the title. Used sparingly — the title usually says enough. */
  eyebrow?: ReactNode;
  id?: string;
  level?: 2 | 3;
  className?: string;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className={cn("mb-4 flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="mb-1 text-label uppercase text-subtle">{eyebrow}</p> : null}
        <Heading id={id} className="text-subheading text-ink">
          {title}
        </Heading>
        {description ? <p className="mt-1 text-small text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
