"use client";

import { errorMessage, useT } from "@carebridge/i18n";
import type { PrescriptionCreate, PrescriptionItemInput } from "@carebridge/shared-types";
import { Alert, Button, Field, TextArea, TextInput } from "@carebridge/ui";
import { useState, type FormEvent } from "react";

const REQUIRED = ["medication", "dosage", "frequency", "duration"] as const;
type RequiredField = (typeof REQUIRED)[number];

const blankItem = (): PrescriptionItemInput => ({ medication: "", dosage: "", frequency: "", duration: "", instructions: "" });

export function validateItems(items: PrescriptionItemInput[]): Record<number, RequiredField[]> {
  const errors: Record<number, RequiredField[]> = {};
  items.forEach((item, i) => {
    const missing = REQUIRED.filter((f) => !item[f].trim());
    if (missing.length) errors[i] = missing;
  });
  return errors;
}

/**
 * Manual, doctor-authored prescription entry. There is deliberately no
 * suggestion, autocomplete, dose checking or AI assistance here.
 */
export function PrescriptionForm({ onSubmit }: { onSubmit: (data: PrescriptionCreate) => Promise<void> }) {
  const t = useT();
  const [items, setItems] = useState<PrescriptionItemInput[]>([blankItem()]);
  const [instructions, setInstructions] = useState("");
  const [errors, setErrors] = useState<Record<number, RequiredField[]>>({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<unknown>(null);
  const [issued, setIssued] = useState(false);

  const update = (i: number, field: keyof PrescriptionItemInput, value: string) => {
    setIssued(false);
    setItems((prev) => prev.map((item, idx) => (idx === i ? { ...item, [field]: value } : item)));
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found = validateItems(items);
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    setServerError(null);
    try {
      await onSubmit({
        items: items.map((i) => ({
          medication: i.medication.trim(),
          dosage: i.dosage.trim(),
          frequency: i.frequency.trim(),
          duration: i.duration.trim(),
          instructions: i.instructions?.trim() || null,
        })),
        instructions: instructions.trim() || null,
      });
      setItems([blankItem()]);
      setInstructions("");
      setIssued(true);
    } catch (err) {
      setServerError(err);
    } finally {
      setBusy(false);
    }
  }

  const fieldError = (i: number, f: RequiredField) => (errors[i]?.includes(f) ? t("case.required") : undefined);

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {items.map((item, i) => (
        <fieldset key={i} className="rounded-md border border-line bg-sunken p-3.5">
          <legend className="px-1 text-small font-semibold">{t("case.item", { n: i + 1 })}</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("prescription.medication")} error={fieldError(i, "medication")} className="sm:col-span-2">
              {(p) => (
                <TextInput
                  {...p}
                  autoComplete="off"
                  maxLength={200}
                  value={item.medication}
                  onChange={(e) => update(i, "medication", e.target.value)}
                />
              )}
            </Field>
            {(["dosage", "frequency", "duration"] as const).map((f) => (
              <Field key={f} label={t(`prescription.${f}`)} error={fieldError(i, f)}>
                {(p) => (
                  <TextInput {...p} autoComplete="off" maxLength={100} value={item[f]} onChange={(e) => update(i, f, e.target.value)} />
                )}
              </Field>
            ))}
            <Field label={t("prescription.instructions")}>
              {(p) => (
                <TextInput
                  {...p}
                  autoComplete="off"
                  maxLength={1000}
                  value={item.instructions ?? ""}
                  onChange={(e) => update(i, "instructions", e.target.value)}
                />
              )}
            </Field>
          </div>
          {items.length > 1 ? (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 text-danger hover:bg-danger-soft"
              onClick={() => {
                setItems((prev) => prev.filter((_, idx) => idx !== i));
                setErrors({});
              }}
            >
              {t("case.removeItem")}
            </Button>
          ) : null}
        </fieldset>
      ))}
      <div>
        <Button variant="secondary" size="sm" onClick={() => setItems((prev) => [...prev, blankItem()])}>
          {t("case.addItem")}
        </Button>
      </div>
      <Field label={t("case.generalInstructions")}>
        {(p) => (
          <TextArea {...p} rows={2} maxLength={4000} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        )}
      </Field>
      {serverError ? <Alert tone="error">{errorMessage(t, serverError)}</Alert> : null}
      {issued ? <Alert tone="success">{t("case.issued")}</Alert> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? t("case.issuing") : t("case.issue")}
        </Button>
        <span className="text-small text-muted">{t("case.issueWarning")}</span>
      </div>
    </form>
  );
}
