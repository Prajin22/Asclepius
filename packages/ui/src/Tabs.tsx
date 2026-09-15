"use client";

import { cn } from "./cn";

export interface SegmentItem<T extends string> {
  value: T;
  label: string;
  /** Small count shown after the label — pages, items, cases. */
  badge?: number;
}

/**
 * A row of tabs along a crease: the selected one is pressed (a solid ink edge),
 * the rest sit on the line. Scrolls horizontally rather than wrapping, so a long
 * set never pushes content down on a phone.
 */
export function SegmentedTabs<T extends string>({
  items,
  value,
  onChange,
  label,
  className,
  size = "md",
}: {
  items: SegmentItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "flex gap-5 overflow-x-auto border-b border-line [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      {items.map((item) => {
        const selected = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.value)}
            className={cn(
              "-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 font-semibold transition-colors duration-150",
              // 44px on a phone, compact where there is a pointer.
              size === "sm" ? "min-h-11 text-small sm:min-h-9" : "min-h-11 text-body sm:min-h-10",
              selected ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {item.label}
            {item.badge !== undefined ? (
              <span className={cn("tabular text-small", selected ? "text-ink" : "text-subtle")}>{item.badge}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
