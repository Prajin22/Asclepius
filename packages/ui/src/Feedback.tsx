"use client";

import { errorMessage, useT } from "@carebridge/i18n";
import { CheckCircle, Info, Warning, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { Button } from "./Button";
import { cn } from "./cn";

type AlertTone = "info" | "success" | "warning" | "error";

const alertTones: Record<AlertTone, { className: string; icon: typeof Info }> = {
  info: { className: "border-info/25 bg-info-soft text-info", icon: Info },
  success: { className: "border-success/25 bg-success-soft text-success", icon: CheckCircle },
  warning: { className: "border-warning/30 bg-warning-soft text-warning", icon: Warning },
  error: { className: "border-danger/30 bg-danger-soft text-danger", icon: WarningCircle },
};

/** A notice. The icon is not decoration: no state in this product is carried by colour alone. */
export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const { className: toneClass, icon: Glyph } = alertTones[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("flex gap-2.5 rounded-md border px-3.5 py-3 text-small", toneClass, className)}
    >
      <Glyph size={17} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title ? "mt-0.5" : undefined)}>{children}</div> : null}
      </div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent", className)}
    />
  );
}

/**
 * Work in progress. The label is the point: a patient should read what is
 * happening ("Reading your document"), not watch an anonymous spinner.
 */
export function LoadingState({ label }: { label?: string }) {
  const t = useT();
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-muted">
      <Spinner />
      <span>{label ?? t("state.loading")}</span>
    </div>
  );
}

/**
 * An empty screen answers three questions: what is empty, why it matters, and
 * what to do next. The action is part of the state, not an afterthought.
 */
export function EmptyState({
  title,
  children,
  action,
  className,
}: {
  title?: ReactNode;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-md border border-dashed border-line-strong bg-sunken/70 px-5 py-6", className)}>
      {title ? <p className="text-subheading text-ink">{title}</p> : null}
      <p className={cn("text-muted", title ? "mt-1" : undefined)}>{children}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/**
 * Something failed. It names what went wrong in the patient's language, says
 * their material is untouched, and offers the way forward.
 */
export function ErrorState({
  error,
  onRetry,
  note,
}: {
  error: unknown;
  onRetry?: () => void;
  /** Overrides the default reassurance, e.g. "Your original file is safe." */
  note?: ReactNode;
}) {
  const t = useT();
  return (
    <Alert tone="error" title={errorMessage(t, error)} className="my-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span>{note ?? t("state.errorNote")}</span>
        {onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            {t("actions.retry")}
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  back,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** A link back to where this page came from. Not a label above the title. */
  back?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {back ? <div className="mb-2 text-small">{back}</div> : null}
        <h1 className="text-page text-balance text-ink">{title}</h1>
        {description ? <p className="mt-1.5 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
