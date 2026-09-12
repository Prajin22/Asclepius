"use client";

import { cn } from "./cn";

export interface SegmentItem<T extends string> {
  value: T;
  label: string;
  /** Small count shown after the label — pages, items, cases. */
  badge?: number;
}

/**
 * A segmented switch for one visible region: document pages, case sections.
 * Scrolls horizontally rather than wrapping, so a long set never pushes content
 * down on a phone.
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
        "-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
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
              "inline-flex shrink-0 items-center gap-2 rounded-full border font-semibold transition-colors duration-150",
              size === "sm" ? "min-h-9 px-3.5 text-small" : "min-h-10 px-4 text-body",
              selected
                ? "border-brand bg-brand text-white"
                : "border-line bg-surface text-muted hover:border-brand/40 hover:text-ink",
            )}
          >
            {item.label}
            {item.badge !== undefined ? (
              <span
                className={cn(
                  "tabular rounded-full px-1.5 text-caption",
                  selected ? "bg-white/20 text-white" : "bg-sunken text-muted",
                )}
              >
                {item.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
