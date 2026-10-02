import { cn } from "@carebridge/ui";
import { SaktiMarkIcon } from "@/components/icons";

/**
 * The product's wordmark, "Asclepius" (PRODUCT=ip_sakti). Typographic on
 * purpose: the name is the identity, and no emblem here suggests a seal, a
 * crest or any official standing the product does not have. `compact` is kept
 * for callers; the one-word name needs no shorter form.
 */
export function SaktiMark({
  className,
  iconOnly = false,
}: {
  className?: string;
  /** Accepted for existing callers; the name is already one word. */
  compact?: boolean;
  /** Just the square, for the narrowest phones; the link around it carries the name. */
  iconOnly?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-ink", className)}>
      <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-md bg-brand text-white">
        <SaktiMarkIcon size={18} weight="bold" />
      </span>
      {iconOnly ? null : (
        <span className="whitespace-nowrap text-subheading font-bold leading-none tracking-tight">Asclepius</span>
      )}
    </span>
  );
}
