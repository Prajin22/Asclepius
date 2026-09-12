"use client";

import { useT } from "@carebridge/i18n";
import { SHARE_CATEGORIES, type ShareCategory } from "@carebridge/shared-types";
import { Badge, Checkbox, cn } from "@carebridge/ui";
import { useEffect, useId, useRef } from "react";
import type { SelectionState, ShareItem } from "@/lib/sharing";

/**
 * Patient-controlled sharing: category checkboxes select/clear all items in
 * the category; individual items can be toggled. Nothing is shared implicitly.
 */
export function ShareSelector({
  items,
  value,
  onChange,
}: {
  items: Record<ShareCategory, ShareItem[]>;
  value: SelectionState;
  onChange: (next: SelectionState) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {SHARE_CATEGORIES.map((category) => (
        <CategoryBlock
          key={category}
          category={category}
          items={items[category]}
          selected={value[category]}
          onChange={(ids) => onChange({ ...value, [category]: ids })}
        />
      ))}
    </div>
  );
}

function CategoryBlock({
  category,
  items,
  selected,
  onChange,
}: {
  category: ShareCategory;
  items: ShareItem[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const t = useT();
  const id = useId();
  const boxRef = useRef<HTMLInputElement>(null);
  const all = items.length > 0 && selected.length === items.length;
  const some = selected.length > 0 && !all;

  useEffect(() => {
    if (boxRef.current) boxRef.current.indeterminate = some;
  }, [some]);

  const toggleItem = (itemId: string, checked: boolean) =>
    onChange(checked ? [...selected, itemId] : selected.filter((x) => x !== itemId));

  return (
    <fieldset
      aria-labelledby={`${id}-label`}
      className={cn(
        "rounded-xl border bg-surface",
        selected.length > 0 ? "border-brand/40" : "border-line",
      )}
    >
      <label
        htmlFor={id}
        className={cn(
          "flex min-h-14 items-center gap-3 px-4 py-3",
          items.length === 0 ? "cursor-not-allowed" : "cursor-pointer",
          items.length > 0 && "border-b border-line",
        )}
      >
        <input
          ref={boxRef}
          id={id}
          type="checkbox"
          className="size-5 shrink-0 accent-[var(--color-brand)]"
          checked={all}
          disabled={items.length === 0}
          onChange={(e) => onChange(e.target.checked ? items.map((i) => i.id) : [])}
        />
        <span id={`${id}-label`} className="flex-1 text-body font-semibold text-ink">
          {t(`shareCategories.${category}`)}
        </span>
        <Badge tone={selected.length > 0 ? "brand" : "neutral"}>{t("request.selected", { count: selected.length })}</Badge>
      </label>
      {items.length === 0 ? (
        <p className="px-4 py-3 text-small text-muted">{t("request.noItems")}</p>
      ) : (
        <ul className="flex flex-col gap-0.5 p-2">
          {items.map((item) => (
            <li key={item.id}>
              <Checkbox
                variant="row"
                label={<span lang={item.lang ?? undefined}>{item.label}</span>}
                description={item.description}
                checked={selected.includes(item.id)}
                onChange={(checked) => toggleItem(item.id, checked)}
              />
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
