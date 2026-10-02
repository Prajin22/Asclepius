"use client";

import { errorMessage, useT } from "@carebridge/i18n";
import {
  ADMINISTRATION_ROUTES,
  LANGUAGES,
  type AdministrationRoute,
  type LanguageCode,
  type ProductFields,
  type ProductIngredient,
  type ProductProfile,
} from "@carebridge/shared-types";
import { Alert, Button, Field, Select, TextArea, TextInput, cn } from "@carebridge/ui";
import { CaretDown, CheckCircle, Circle, Plus, X } from "@phosphor-icons/react/dist/ssr";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { NeedTag } from "../ui";

const EMPTY: ProductFields = { name: "", ingredients: [], markers: [] };

function fromProfile(p: ProductProfile): ProductFields {
  return {
    name: p.name,
    intended_use: p.intended_use,
    dosage_form: p.dosage_form,
    administration_route: p.administration_route,
    ingredients: p.ingredients.map((i) => ({ ...i })),
    preparation_method: p.preparation_method,
    classical_reference: p.classical_reference,
    extract_description: p.extract_description,
    standardization_description: p.standardization_description,
    markers: [...p.markers],
    notes: p.notes,
    text_language: p.text_language,
  };
}

/** Blank text becomes null, blank rows are dropped: the profile holds what was actually written. */
export function clean(values: ProductFields): ProductFields {
  const text = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
  return {
    name: values.name.trim(),
    intended_use: text(values.intended_use),
    dosage_form: text(values.dosage_form),
    administration_route: values.administration_route ?? null,
    ingredients: (values.ingredients ?? [])
      .filter((i) => i.name.trim())
      .map((i) => ({ name: i.name.trim(), part_used: text(i.part_used), quantity: text(i.quantity) })),
    preparation_method: text(values.preparation_method),
    classical_reference: text(values.classical_reference),
    extract_description: text(values.extract_description),
    standardization_description: text(values.standardization_description),
    markers: (values.markers ?? []).map((m) => m.trim()).filter(Boolean),
    notes: text(values.notes),
    text_language: values.text_language ?? null,
  };
}

/** The nine sections, in order. The first four are the essentials and always open. */
const SECTIONS = [
  { key: "identity", fields: ["name", "text_language"], essential: true },
  { key: "purpose", fields: ["intended_use"], essential: true },
  { key: "form", fields: ["dosage_form", "administration_route"], essential: true },
  { key: "ingredients", fields: ["ingredients"], essential: true },
  { key: "preparation", fields: ["preparation_method"], essential: false },
  { key: "classical", fields: ["classical_reference"], essential: false },
  { key: "extract", fields: ["extract_description", "standardization_description"], essential: false },
  { key: "markers", fields: ["markers"], essential: false },
  { key: "notes", fields: ["notes"], essential: false },
] as const satisfies readonly { key: string; fields: readonly (keyof ProductFields)[]; essential: boolean }[];

type SectionKey = (typeof SECTIONS)[number]["key"];

function filled(values: ProductFields, fields: readonly (keyof ProductFields)[]): boolean {
  const c = clean(values);
  return fields.some((f) => {
    const v = c[f];
    return Array.isArray(v) ? v.length > 0 : v != null && v !== "";
  });
}

/**
 * A product described in the user's own words, in nine sections. Descriptive
 * facts only: there is no field for a category, a schedule or any conclusion —
 * those come from the classifier's questions, answered separately and kept
 * apart. The optional sections open on request; an edit opens every section
 * that already holds something.
 */
export function ProductEditor({
  product,
  onSubmit,
  onCancel,
}: {
  product?: ProductProfile;
  onSubmit: (values: ProductFields, then: "view" | "classify") => Promise<unknown>;
  onCancel?: () => void;
}) {
  const t = useT();
  const initial = useMemo(() => (product ? fromProfile(product) : { ...EMPTY }), [product]);
  const [values, setValues] = useState<ProductFields>(initial);
  const [open, setOpen] = useState<Set<SectionKey>>(
    () => new Set(SECTIONS.filter((s) => s.essential || filled(initial, s.fields)).map((s) => s.key)),
  );
  const [busy, setBusy] = useState<"view" | "classify" | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tried, setTried] = useState(false);
  const [touched, setTouched] = useState<Set<string>>(new Set());

  const set = <K extends keyof ProductFields>(key: K, value: ProductFields[K]) => setValues((v) => ({ ...v, [key]: value }));
  const touch = (key: string) => setTouched((s) => new Set(s).add(key));
  const ingredients = values.ingredients ?? [];
  const markers = values.markers ?? [];
  const dirty = JSON.stringify(clean(values)) !== JSON.stringify(clean(initial));

  // Leaving with unsaved changes asks first.
  useEffect(() => {
    if (!dirty || busy) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, busy]);

  const nameError = (tried || touched.has("name")) && !values.name.trim() ? t("product.validation.name") : undefined;
  // A row with a part or quantity but no name would be dropped silently on save; say so instead.
  const badRow = (row: ProductIngredient) => !row.name.trim() && Boolean(row.part_used?.trim() || row.quantity?.trim());
  const rowError = (row: ProductIngredient, index: number) =>
    (tried || touched.has(`ingredient-${index}`)) && badRow(row) ? t("product.validation.ingredient") : undefined;
  const invalid = !values.name.trim() || ingredients.some(badRow);

  async function submit(then: "view" | "classify", e?: FormEvent) {
    e?.preventDefault();
    setTried(true);
    if (invalid) {
      if (!values.name.trim()) document.querySelector<HTMLInputElement>('[data-field="name"]')?.focus();
      return;
    }
    setBusy(then);
    setError(null);
    try {
      await onSubmit(clean(values), then);
    } catch (err) {
      setError(err);
      setBusy(null);
    }
  }

  const toggle = (key: SectionKey) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const text = (key: keyof ProductFields, opts: { area?: boolean; max: number; rows?: number }) => (
    <Field label={t(`product.field.${key}`)} hint={t(`product.hint.${key}`)}>
      {(p) =>
        opts.area ? (
          <TextArea
            {...p}
            rows={opts.rows ?? 3}
            maxLength={opts.max}
            value={(values[key] as string | null) ?? ""}
            onChange={(e) => set(key, e.target.value as never)}
          />
        ) : (
          <TextInput
            {...p}
            maxLength={opts.max}
            value={(values[key] as string | null) ?? ""}
            onChange={(e) => set(key, e.target.value as never)}
          />
        )
      }
    </Field>
  );

  const body: Record<SectionKey, ReactNode> = {
    identity: (
      <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Field
          label={
            <span className="flex items-baseline gap-2">
              {t("product.field.name")} <NeedTag required />
            </span>
          }
          hint={t("product.hint.name")}
          error={nameError}
        >
          {(p) => (
            <TextInput
              {...p}
              data-field="name"
              required
              maxLength={200}
              value={values.name}
              onChange={(e) => set("name", e.target.value)}
              onBlur={() => touch("name")}
            />
          )}
        </Field>
        <Field label={t("product.field.text_language")} hint={t("product.hint.text_language")}>
          {(p) => (
            <Select
              {...p}
              value={values.text_language ?? ""}
              onChange={(e) => set("text_language", (e.target.value || null) as LanguageCode | null)}
            >
              <option value="">{t("product.none")}</option>
              {LANGUAGES.map((language) => (
                <option key={language.code} value={language.code} lang={language.code}>
                  {language.nativeName}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
    ),
    purpose: text("intended_use", { area: true, max: 2000 }),
    form: (
      <div className="grid gap-4 sm:grid-cols-2">
        {text("dosage_form", { max: 200 })}
        <Field label={t("product.field.administration_route")} hint={t("product.hint.administration_route")}>
          {(p) => (
            <Select
              {...p}
              value={values.administration_route ?? ""}
              onChange={(e) => set("administration_route", (e.target.value || null) as AdministrationRoute | null)}
            >
              <option value="">{t("product.none")}</option>
              {ADMINISTRATION_ROUTES.map((route) => (
                <option key={route} value={route}>
                  {t(`product.route.${route}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
    ),
    ingredients: (
      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">{t("product.field.ingredients")}</legend>
        <p className="text-small text-muted">{t("product.hint.ingredients")}</p>
        {ingredients.map((row, index) => {
          const err = rowError(row, index);
          return (
            <div key={index} className={cn("rounded-md border bg-sunken/50 p-3", err ? "border-danger/50" : "border-line")}>
              <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
                <Field label={t("product.ingredient.name")} error={err}>
                  {(p) => (
                    <TextInput
                      {...p}
                      maxLength={200}
                      value={row.name}
                      onChange={(e) => setIngredient(index, { name: e.target.value })}
                      onBlur={() => touch(`ingredient-${index}`)}
                    />
                  )}
                </Field>
                <Field label={t("product.ingredient.part_used")}>
                  {(p) => (
                    <TextInput {...p} maxLength={200} value={row.part_used ?? ""} onChange={(e) => setIngredient(index, { part_used: e.target.value })} />
                  )}
                </Field>
                <Field label={t("product.ingredient.quantity")}>
                  {(p) => (
                    <TextInput {...p} maxLength={100} value={row.quantity ?? ""} onChange={(e) => setIngredient(index, { quantity: e.target.value })} />
                  )}
                </Field>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={t("product.ingredient.remove", { number: index + 1 })}
                  onClick={() => set("ingredients", ingredients.filter((_, i) => i !== index))}
                  className="justify-self-start"
                >
                  <X size={16} aria-hidden />
                  <span className="sm:sr-only">{t("product.remove")}</span>
                </Button>
              </div>
            </div>
          );
        })}
        <div>
          <Button variant="secondary" size="sm" onClick={() => set("ingredients", [...ingredients, { name: "" }])}>
            <Plus size={16} aria-hidden />
            {t("product.ingredient.add")}
          </Button>
        </div>
      </fieldset>
    ),
    preparation: text("preparation_method", { area: true, max: 5000, rows: 4 }),
    classical: text("classical_reference", { max: 300 }),
    extract: (
      <div className="grid gap-4 md:grid-cols-2">
        {text("extract_description", { area: true, max: 2000 })}
        {text("standardization_description", { area: true, max: 2000 })}
      </div>
    ),
    markers: (
      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">{t("product.field.markers")}</legend>
        <p className="text-small text-muted">{t("product.hint.markers")}</p>
        {markers.map((marker, index) => (
          <div key={index} className="flex items-end gap-2">
            <Field label={t("product.marker.name")} className="flex-1">
              {(p) => (
                <TextInput
                  {...p}
                  maxLength={200}
                  value={marker}
                  onChange={(e) => set("markers", markers.map((m, i) => (i === index ? e.target.value : m)))}
                />
              )}
            </Field>
            <Button
              variant="ghost"
              size="sm"
              aria-label={t("product.marker.remove", { number: index + 1 })}
              onClick={() => set("markers", markers.filter((_, i) => i !== index))}
            >
              <X size={16} aria-hidden />
            </Button>
          </div>
        ))}
        <div>
          <Button variant="secondary" size="sm" onClick={() => set("markers", [...markers, ""])}>
            <Plus size={16} aria-hidden />
            {t("product.marker.add")}
          </Button>
        </div>
      </fieldset>
    ),
    notes: text("notes", { area: true, max: 2000 }),
  };

  function setIngredient(index: number, patch: Partial<ProductIngredient>) {
    set("ingredients", ingredients.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  return (
    <form onSubmit={(e) => submit("view", e)} noValidate className="grid gap-6 xl:grid-cols-[13rem_minmax(0,1fr)]">
      <nav aria-label={t("product.sectionsNav")} className="hidden xl:block">
        <ol className="sticky top-24 flex flex-col gap-0.5 text-small">
          {SECTIONS.map((s, i) => {
            const done = filled(values, s.fields);
            return (
              <li key={s.key}>
                <a
                  href={`#product-section-${s.key}`}
                  onClick={() => setOpen((o) => new Set(o).add(s.key))}
                  className="flex min-h-9 items-center gap-2 rounded-md px-2.5 text-muted hover:bg-sunken hover:text-ink"
                >
                  {done ? (
                    <CheckCircle size={16} weight="fill" aria-hidden className="shrink-0 text-success" />
                  ) : (
                    <Circle size={16} aria-hidden className="shrink-0 text-subtle" />
                  )}
                  <span className="min-w-0 flex-1 truncate">
                    {i + 1}. {t(`product.section.${s.key}.title`)}
                  </span>
                  <span className="sr-only">{t(done ? "product.sectionFilled" : "product.sectionEmpty")}</span>
                </a>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="flex min-w-0 flex-col gap-4">
        <Alert tone="info">{t("product.factsNote")}</Alert>

        {SECTIONS.map((s, i) => {
          const expanded = open.has(s.key);
          const headingId = `product-section-${s.key}`;
          const panelId = `${headingId}-panel`;
          const has = filled(values, s.fields);
          return (
            <section
              key={s.key}
              aria-labelledby={`${headingId}-title`}
              id={headingId}
              className="scroll-mt-24 rounded-md border border-line bg-surface"
            >
              <header className="flex items-start gap-3 px-5 py-4 sm:px-6">
                <span
                  aria-hidden
                  className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-small font-bold text-brand-strong"
                >
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 id={`${headingId}-title`} className="flex flex-wrap items-baseline gap-x-2 text-subheading text-ink">
                    {s.essential ? (
                      t(`product.section.${s.key}.title`)
                    ) : (
                      <button
                        type="button"
                        aria-expanded={expanded}
                        aria-controls={panelId}
                        onClick={() => toggle(s.key)}
                        className="inline-flex items-center gap-1.5 rounded-sm text-left hover:text-brand-strong"
                      >
                        {t(`product.section.${s.key}.title`)}
                        <CaretDown
                          size={16}
                          aria-hidden
                          className={cn("transition-transform duration-150", expanded ? "rotate-180" : undefined)}
                        />
                      </button>
                    )}
                    <NeedTag required={s.key === "identity"} />
                  </h2>
                  <p className="mt-0.5 text-small text-muted">{t(`product.section.${s.key}.hint`)}</p>
                  {!expanded && has ? <p className="mt-1 text-caption font-medium text-success">{t("product.sectionFilled")}</p> : null}
                </div>
              </header>
              {expanded ? (
                <div id={panelId} className="border-t border-line px-5 py-4 sm:px-6 sm:py-5">
                  {body[s.key]}
                </div>
              ) : null}
            </section>
          );
        })}

        {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
        {tried && invalid ? <Alert tone="error">{t("product.validation.summary")}</Alert> : null}

        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-line bg-surface px-4 py-3 sm:mx-0 sm:rounded-md sm:border sm:shadow-md">
          <p role="status" className="flex items-center gap-2 text-small font-medium">
            {dirty ? (
              <>
                <span aria-hidden className="size-2 rounded-full bg-warning" />
                <span className="text-warning">{t("product.unsaved")}</span>
              </>
            ) : (
              <span className="text-subtle">{t(product ? "product.noChanges" : "product.nothingYet")}</span>
            )}
          </p>
          {/* On a phone the bar is two lines: the status, then the actions side by side. Back is at the top of the page. */}
          <div className="flex gap-2 max-sm:w-full">
            {onCancel ? (
              <Button variant="ghost" onClick={onCancel} disabled={busy !== null} className="max-sm:hidden">
                {t("product.cancel")}
              </Button>
            ) : null}
            {product ? null : (
              <Button variant="secondary" onClick={() => submit("classify")} disabled={busy !== null} className="max-sm:flex-1">
                {busy === "classify" ? t("product.saving") : t("product.createAndClassify")}
              </Button>
            )}
            <Button type="submit" disabled={busy !== null || (product !== undefined && !dirty)} className="max-sm:flex-1">
              {busy === "view" ? t("product.saving") : product ? t("product.save") : t("product.create")}
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
