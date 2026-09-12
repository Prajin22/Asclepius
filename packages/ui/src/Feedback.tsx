"use client";

import { errorMessage, useT } from "@carebridge/i18n";
import type { ReactNode } from "react";
import { Button } from "./Button";
import { cn } from "./cn";

type AlertTone = "info" | "success" | "warning" | "error";

const alertTones: Record<AlertTone, string> = {
  info: "border-info/25 bg-info-soft text-info",
  success: "border-success/25 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  error: "border-danger/30 bg-danger-soft text-danger",
};

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
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("rounded-lg border px-4 py-3 text-small", alertTones[tone], className)}
    >
      {title ? <p className="font-semibold">{title}</p> : null}
      {children ? <div className={cn(title ? "mt-0.5" : undefined)}>{children}</div> : null}
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

export function LoadingState({ label }: { label?: string }) {
  const t = useT();
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-muted">
      <Spinner />
      <span>{label ?? t("state.loading")}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  return (
    <Alert tone="error" className="my-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span>{errorMessage(t, error)}</span>
        {onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            {t("actions.retry")}
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}

export function EmptyState({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong bg-sunken/60 px-4 py-6 text-center text-muted">
      <p>{children}</p>
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow ? <div className="mb-2 text-small">{eyebrow}</div> : null}
        <h1 className="text-heading text-balance text-ink sm:text-page">{title}</h1>
        {description ? <p className="mt-1.5 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
