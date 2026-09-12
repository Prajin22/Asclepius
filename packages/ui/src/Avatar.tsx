import { cn } from "./cn";

function initials(name: string): string {
  const parts = name
    .replace(/^(dr|prof)\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "?";
  const letters = parts.length === 1 ? parts[0]!.slice(0, 2) : parts[0]![0]! + parts[parts.length - 1]![0]!;
  return letters.toUpperCase();
}

/**
 * Initials stand in for a photo: this is synthetic demo data, and a real
 * deployment should not invent faces for patients or clinicians.
 */
export function Avatar({
  name,
  size = "md",
  tone = "brand",
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  tone?: "brand" | "ink";
  className?: string;
}) {
  const sizes = {
    sm: "size-8 text-caption",
    md: "size-10 text-small",
    lg: "size-14 text-subheading",
  } as const;
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        tone === "brand" ? "bg-brand-soft text-brand-strong" : "bg-ink/[0.06] text-ink",
        sizes[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}
