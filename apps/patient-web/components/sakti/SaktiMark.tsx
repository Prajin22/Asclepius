import { cn } from "@carebridge/ui";
import { SaktiMarkIcon } from "@/components/icons";

/**
 * The IP-SAKTI Sahayak wordmark. Typographic on purpose: the product name is
 * the identity, and no emblem here suggests a seal, a crest or any official
 * standing the product does not have.
 */
export function SaktiMark({
  className,
  compact = false,
  iconOnly = false,
}: {
  className?: string;
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
        <span className="whitespace-nowrap text-subheading leading-none tracking-tight">
          <span className="font-bold">IP-SAKTI</span>
          {compact ? null : <span className="ml-1.5 font-normal text-muted">Sahayak</span>}
        </span>
      )}
    </span>
  );
}
