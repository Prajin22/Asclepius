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
import { Alert, Button, Field, Select, TextArea, TextInput } from "@carebridge/ui";
import { X } from "@phosphor-icons/react/dist/ssr";
import { useState, type FormEvent } from "react";

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
function clean(values: ProductFields): ProductFields {
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

/**
 * A product described in the user's own words. Descriptive facts only: there
 * is no field for a category, a schedule or any conclusion — those come from
 * the classifier's questions, answered separately and kept apart.
 */
export function ProductForm({
  product,
  onSubmit,
  onCancel,
}: {
  product?: ProductProfile;
  onSubmit: (values: ProductFields) => Promise<unknown>;
  onCancel?: () => void;
}) {
  const t = useT();
  const [values, setValues] = useState<ProductFields>(() => (product ? fromProfile(product) : { ...EMPTY }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const set = <K extends keyof ProductFields>(key: K, value: ProductFields[K]) => setValues((v) => ({ ...v, [key]: value }));
  const ingredients = values.ingredients ?? [];
  const markers = values.markers ?? [];

  function setIngredient(index: number, patch: Partial<ProductIngredient>) {
    set("ingredients", ingredients.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(clean(values));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const textField = (key: keyof ProductFields, opts: { area?: boolean; max: number; wide?: boolean }) => (
    <Field label={t(`product.field.${key}`)} className={opts.wide ? "sm:col-span-2" : undefined}>
      {(p) =>
        opts.area ? (
          <TextArea
            {...p}
            rows={3}
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

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <p className="text-small text-muted">{t("product.factsNote")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {textField("name", { max: 200, wide: true })}
        {textField("intended_use", { area: true, max: 2000, wide: true })}
        {textField("dosage_form", { max: 200 })}
        <Field label={t("product.field.administration_route")}>
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

      <fieldset className="flex flex-col gap-3">
        <legend className="text-small font-semibold text-ink">{t("product.field.ingredients")}</legend>
        {ingredients.map((row, index) => (
          <div key={index} className="grid gap-2 rounded-md border border-line p-3 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end">
            <Field label={t("product.ingredient.name")}>
              {(p) => <TextInput {...p} maxLength={200} value={row.name} onChange={(e) => setIngredient(index, { name: e.target.value })} />}
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
              type="button"
              variant="ghost"
              size="sm"
              aria-label={t("product.ingredient.remove", { number: index + 1 })}
              onClick={() => set("ingredients", ingredients.filter((_, i) => i !== index))}
            >
              <X size={16} aria-hidden />
            </Button>
          </div>
        ))}
        <div>
          <Button type="button" variant="secondary" size="sm" onClick={() => set("ingredients", [...ingredients, { name: "" }])}>
            {t("product.ingredient.add")}
          </Button>
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        {textField("preparation_method", { area: true, max: 5000, wide: true })}
        {textField("classical_reference", { max: 300, wide: true })}
        {textField("extract_description", { area: true, max: 2000 })}
        {textField("standardization_description", { area: true, max: 2000 })}
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="text-small font-semibold text-ink">{t("product.field.markers")}</legend>
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
              type="button"
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
          <Button type="button" variant="secondary" size="sm" onClick={() => set("markers", [...markers, ""])}>
            {t("product.marker.add")}
          </Button>
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        {textField("notes", { area: true, max: 2000 })}
        <Field label={t("product.field.text_language")}>
          {(p) => (
            <Select
              {...p}
              value={values.text_language ?? ""}
              onChange={(e) => set("text_language", (e.target.value || null) as LanguageCode | null)}
            >
              <option value="">{t("product.none")}</option>
              {LANGUAGES.map((language) => (
                <option key={language.code} value={language.code}>
                  {language.nativeName}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      {error ? <Alert tone="error">{errorMessage(t, error)}</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !values.name.trim()}>
          {busy ? t("product.saving") : product ? t("product.save") : t("product.create")}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={busy}>
            {t("product.cancel")}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
