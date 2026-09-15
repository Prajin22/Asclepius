import { cn } from "./cn";

/**
 * Loading placeholders shaped like the content that is coming, so the page does
 * not jump when it arrives. Under `prefers-reduced-motion` the shimmer stops
 * (theme.css) and these stay as quiet blocks of paper.
 */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cn("block animate-pulse rounded-sm bg-sunken", className)} />;
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <span aria-hidden className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-3.5", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </span>
  );
}

/** A sheet-shaped placeholder: title, two lines, one action. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md border border-line bg-surface p-5", className)}>
      <Skeleton className="h-4 w-1/3" />
      <SkeletonText className="mt-4" lines={2} />
      <Skeleton className="mt-5 h-9 w-28 rounded-md" />
    </div>
  );
}
