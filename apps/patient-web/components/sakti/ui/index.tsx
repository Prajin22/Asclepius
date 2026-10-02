"use client";

/**
 * IP-SAKTI Sahayak's small UI kit, built on the shared primitives
 * (@carebridge/ui) and the IP-SAKTI theme layer (app/globals.css). See
 * docs/IP_SAKTI_UI_SYSTEM.md.
 *
 * Rules every piece follows: no state is carried by colour alone (each has an
 * icon and a word); synthetic data is always labelled; India and International
 * are told apart by name, icon and rule, not hue; nothing here looks like an
 * official seal.
 */
import { useT } from "@carebridge/i18n";
import { Badge, cn, type Tone } from "@carebridge/ui";
import {
  ArrowRight,
  CheckCircle,
  CircleDashed,
  Clock,
  Flask,
  GlobeHemisphereWest,
  HourglassMedium,
  MapPinArea,
  Question,
  SealCheck,
  Warning,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon, IconProps } from "@phosphor-icons/react";
import Link from "next/link";
import { useId, type ReactNode } from "react";

/** Any icon: a Phosphor icon or one of the app's wrappers around one. */
export type Glyph = (props: IconProps) => ReactNode;

// ---------------------------------------------------------------------------
// Product classification state
// ---------------------------------------------------------------------------

export type ProductState = "not_classified" | "in_progress" | "requires_information" | "awaiting_confirmation" | "confirmed";

const STATE: Record<ProductState, { tone: Tone; icon: Icon }> = {
  not_classified: { tone: "neutral", icon: CircleDashed },
  in_progress: { tone: "info", icon: HourglassMedium },
  requires_information: { tone: "warning", icon: Question },
  awaiting_confirmation: { tone: "brand", icon: Clock },
  confirmed: { tone: "success", icon: SealCheck },
};

/** Where a product's classification stands — icon, word and tone together. */
export function StateBadge({ state, className }: { state: ProductState; className?: string }) {
  const t = useT();
  const { tone, icon: Glyph } = STATE[state];
  return (
    <Badge tone={tone} className={className}>
      <Glyph size={13} weight="bold" aria-hidden />
      {t(`ui.state.${state}`)}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Lanes
// ---------------------------------------------------------------------------

export type Lane = "india" | "international";

const LANE: Record<Lane, { icon: Icon; text: string; soft: string; rule: string }> = {
  india: { icon: MapPinArea, text: "text-lane-india", soft: "bg-lane-india-soft", rule: "border-l-4 border-l-lane-india" },
  international: {
    icon: GlobeHemisphereWest,
    text: "text-lane-intl",
    soft: "bg-lane-intl-soft",
    rule: "border-l-[6px] border-l-lane-intl [border-left-style:double]",
  },
};

/** A lane named in words with its own icon; colour is the third cue, not the first. */
export function LaneMark({ lane, size = "md", className }: { lane: Lane; size?: "sm" | "md"; className?: string }) {
  const t = useT();
  const { icon: Glyph, text, soft } = LANE[lane];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm font-semibold uppercase tracking-[0.06em]",
        size === "sm" ? "px-1.5 py-0.5 text-caption" : "px-2 py-1 text-small",
        text,
        soft,
        className,
      )}
    >
      <Glyph size={size === "sm" ? 13 : 16} weight="bold" aria-hidden />
      {t(`ui.lane.${lane}`)}
    </span>
  );
}

/** The ruled edge a lane's panel carries: solid for India, double for International. */
export function laneRule(lane: Lane): string {
  return LANE[lane].rule;
}

// ---------------------------------------------------------------------------
// Demo data
// ---------------------------------------------------------------------------

/** Marks synthetic demonstration data. Never on anything official or real. */
export function DemoTag({ className, label }: { className?: string; label?: string }) {
  const t = useT();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-dashed border-demo/60 bg-demo-soft px-1.5 py-0.5",
        "text-caption font-bold uppercase tracking-[0.08em] text-demo",
        className,
      )}
    >
      <Flask size={12} weight="bold" aria-hidden />
      {label ?? t("ui.demo.tag")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Numbers and progress
// ---------------------------------------------------------------------------

export function StatTile({
  label,
  value,
  icon: Glyph,
  hint,
  tone = "neutral",
  href,
}: {
  label: string;
  value: number | string;
  icon: Glyph;
  hint?: string;
  tone?: "neutral" | "brand" | "info" | "success" | "warning" | "danger";
  href?: string;
}) {
  const accents = {
    neutral: "text-muted bg-sunken",
    brand: "text-brand-strong bg-brand-soft",
    info: "text-info bg-info-soft",
    success: "text-success bg-success-soft",
    warning: "text-warning bg-warning-soft",
    danger: "text-danger bg-danger-soft",
  } as const;
  const body = (
    <>
      <span className={cn("grid size-9 shrink-0 place-items-center rounded-md", accents[tone])}>
        <Glyph size={18} weight="bold" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block text-small font-medium text-muted [overflow-wrap:anywhere]">{label}</span>
        <span data-value className="block text-value text-ink">
          {value}
        </span>
        {hint ? <span className="block text-caption text-subtle">{hint}</span> : null}
      </span>
    </>
  );
  const shell = "flex items-start gap-3 rounded-md border border-line bg-surface p-4";
  return href ? (
    <Link href={href} className={cn(shell, "transition-shadow duration-150 hover:shadow-sm")}>
      {body}
    </Link>
  ) : (
    <div className={shell}>{body}</div>
  );
}

/** "Step 2 of 4" with a segmented track. The text is the progress; the track repeats it. */
export function StepProgress({ step, total, label }: { step: number; total: number; label: string }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-2">
      <p id={id} className="text-small font-semibold text-brand-strong">
        {label}
      </p>
      <div
        role="progressbar"
        aria-labelledby={id}
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={step}
        aria-valuetext={label}
        className="flex gap-1.5"
      >
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors duration-200",
              i < step ? "bg-brand" : "bg-line",
            )}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Choosing
// ---------------------------------------------------------------------------

/**
 * One answer as a card: a real radio input under a large target. The "unknown"
 * kind is dashed and neutral — clearly different, never alarming.
 */
export function ChoiceCard({
  name,
  value,
  checked,
  onChange,
  title,
  hint,
  kind = "answer",
}: {
  name: string;
  value: string;
  checked: boolean;
  onChange: (value: string) => void;
  title: string;
  hint?: string;
  kind?: "answer" | "unknown";
}) {
  return (
    <label
      className={cn(
        "group flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3.5 transition-[border-color,background-color,box-shadow] duration-150",
        kind === "unknown"
          ? checked
            ? "border-dashed border-ink/50 bg-sunken"
            : "border-dashed border-line-strong bg-surface hover:bg-sunken"
          : checked
            ? "border-brand bg-brand-tint shadow-xs ring-1 ring-brand"
            : "border-line bg-surface hover:border-brand/50 hover:bg-brand-tint/60",
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={() => onChange(value)}
        className="mt-1 size-5 shrink-0 accent-[var(--color-brand)]"
      />
      <span className="min-w-0">
        <span className={cn("block font-semibold", kind === "unknown" ? "text-muted" : "text-ink")}>{title}</span>
        {hint ? <span className="mt-0.5 block text-small text-muted">{hint}</span> : null}
      </span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Sections, empties, later releases
// ---------------------------------------------------------------------------

/** A numbered section of a longer form or page. */
export function SectionCard({
  number,
  title,
  hint,
  tag,
  id,
  children,
  className,
}: {
  number?: number;
  title: string;
  hint?: string;
  tag?: ReactNode;
  id?: string;
  children: ReactNode;
  className?: string;
}) {
  const headingId = id ?? `section-${number ?? title}`;
  return (
    <section aria-labelledby={headingId} className={cn("rounded-md border border-line bg-surface", className)}>
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-5 py-4 sm:px-6">
        <div className="flex min-w-0 items-start gap-3">
          {number !== undefined ? (
            <span
              aria-hidden
              className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-small font-bold text-brand-strong"
            >
              {number}
            </span>
          ) : null}
          <div className="min-w-0">
            <h2 id={headingId} className="text-subheading text-ink">
              {title}
            </h2>
            {hint ? <p className="mt-0.5 text-small text-muted">{hint}</p> : null}
          </div>
        </div>
        {tag}
      </header>
      <div className="px-5 py-4 sm:px-6 sm:py-5">{children}</div>
    </section>
  );
}

/** A small "optional" / "required" tag beside a field or section title. */
export function NeedTag({ required }: { required?: boolean }) {
  const t = useT();
  return (
    <span className={cn("text-caption font-semibold", required ? "text-brand-strong" : "text-subtle")}>
      {t(required ? "ui.required" : "ui.optional")}
    </span>
  );
}

export function EmptyPanel({
  icon: Glyph,
  title,
  children,
  action,
  className,
}: {
  icon: Glyph;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-md border border-dashed border-line-strong/60 bg-sunken/60 px-6 py-10 text-center", className)}>
      <span className="grid size-12 place-items-center rounded-full bg-surface text-brand shadow-xs">
        <Glyph size={24} aria-hidden />
      </span>
      <p className="mt-3 text-subheading text-ink">{title}</p>
      {children ? <div className="mt-1 max-w-md text-small text-muted">{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** A capability that exists in the design but not yet in the product. Says so plainly. */
export function LaterRelease({ title, body, points }: { title?: string; body: string; points?: string[] }) {
  const t = useT();
  return (
    <div className="rounded-md border border-dashed border-line-strong/60 bg-sunken/60 p-5">
      <p className="flex items-center gap-2 text-small font-semibold text-muted">
        <Clock size={16} weight="bold" aria-hidden />
        {title ?? t("ui.laterRelease")}
      </p>
      <p className="mt-1.5 text-small text-muted">{body}</p>
      {points?.length ? (
        <ul className="mt-3 flex flex-col gap-1.5 text-small text-ink">
          {points.map((p) => (
            <li key={p} className="flex gap-2">
              <ArrowRight size={14} weight="bold" aria-hidden className="mt-1 shrink-0 text-brand" />
              {p}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** A readiness line: done (check) or not yet (open circle), with words. */
export function ReadinessItem({ done, label, note }: { done: boolean; label: string; note?: string }) {
  const t = useT();
  return (
    <li className="flex items-start gap-3 py-2.5">
      {done ? (
        <CheckCircle size={20} weight="fill" aria-hidden className="mt-0.5 shrink-0 text-success" />
      ) : (
        <CircleDashed size={20} weight="bold" aria-hidden className="mt-0.5 shrink-0 text-subtle" />
      )}
      <span className="min-w-0">
        <span className="block font-medium text-ink">
          {label}
          <span className="sr-only"> — {t(done ? "ui.readiness.done" : "ui.readiness.notYet")}</span>
        </span>
        {note ? <span className="block text-small text-muted">{note}</span> : null}
      </span>
    </li>
  );
}

export function InfoOnly({ className }: { className?: string }) {
  const t = useT();
  return (
    <p className={cn("flex items-start gap-2 text-small text-muted", className)}>
      <Warning size={16} aria-hidden className="mt-0.5 shrink-0" />
      {t("ui.infoOnly")}
    </p>
  );
}
