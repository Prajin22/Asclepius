"use client";

import { useT } from "@carebridge/i18n";
import { SHARE_CATEGORIES, type ShareCategory } from "@carebridge/shared-types";
import { Badge, Checkbox, cn } from "@carebridge/ui";
import { CaretDown, CaretUp } from "@phosphor-icons/react/dist/ssr";
import { useEffect, useId, useRef, useState } from "react";
import type { SelectionState, ShareItem } from "@/lib/sharing";

/**
 * Patient-controlled sharing.
 *
 * Categories arrive folded: the count says what would go, and opening one shows
 * every item so nothing is shared unseen. The category box selects or clears all
 * of its items; each item can still be toggled on its own. Nothing is implicit.
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
    <div className="flex flex-col gap-3">
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
  const [open, setOpen] = useState(false);
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
      className={cn("rounded-md border bg-surface", selected.length > 0 ? "border-brand/45" : "border-line")}
    >
      <div className={cn("flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5", open && items.length > 0 && "border-b border-line")}>
        <input
          ref={boxRef}
          id={id}
          type="checkbox"
          className="size-5 shrink-0 accent-[var(--color-brand)]"
          checked={all}
          disabled={items.length === 0}
          onChange={(e) => onChange(e.target.checked ? items.map((i) => i.id) : [])}
        />
        <label htmlFor={id} id={`${id}-label`} className="flex-1 cursor-pointer text-body font-semibold text-ink">
          {t(`shareCategories.${category}`)}
        </label>
        <Badge tone={selected.length > 0 ? "brand" : "neutral"}>
          {t("request.selectedOf", { count: selected.length, total: items.length })}
        </Badge>
        {items.length > 0 ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={`${id}-items`}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex min-h-11 items-center gap-1 rounded-md px-2 text-small font-semibold text-brand-strong hover:bg-brand-soft sm:min-h-9"
          >
            {open ? <CaretUp size={14} weight="bold" aria-hidden /> : <CaretDown size={14} weight="bold" aria-hidden />}
            {open ? t("request.hideItems") : t("request.showItems")}
          </button>
        ) : null}
      </div>
      {items.length === 0 ? (
        <p className="px-4 pb-3 text-small text-muted">{t("request.noItems")}</p>
      ) : open ? (
        <ul id={`${id}-items`} className="flex flex-col gap-0.5 p-2">
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
      ) : null}
    </fieldset>
  );
}
