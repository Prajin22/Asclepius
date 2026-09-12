import type { ReactNode } from "react";
import { cn } from "./cn";

export function Card({
  children,
  className,
  as: Tag = "section",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
  "aria-labelledby"?: string;
}) {
  return (
    <Tag className={cn("rounded-xl border border-line bg-surface p-5 sm:p-6", className)} {...rest}>
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
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  id?: string;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <Heading id={id} className="text-lg font-semibold leading-snug text-ink">
          {title}
        </Heading>
        {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
