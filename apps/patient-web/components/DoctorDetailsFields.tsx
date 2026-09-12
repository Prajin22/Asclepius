"use client";

import { useT } from "@carebridge/i18n";
import { LANGUAGES, type DoctorAccount, type DoctorDetails, type LanguageCode } from "@carebridge/shared-types";
import { Field, TextArea, TextInput, cn } from "@carebridge/ui";
import { Check } from "@phosphor-icons/react/dist/ssr";
import { useId, type InputHTMLAttributes } from "react";

/** The details an administrator checks, as form state: optional fields are plain strings while editing. */
export interface DoctorDetailsDraft {
  name: string;
  specialization: string;
  qualification: string;
  registration_identifier: string;
  clinic_name: string;
  clinic_address: string;
  phone: string;
  languages: LanguageCode[];
}

export const EMPTY_DOCTOR_DETAILS: DoctorDetailsDraft = {
  name: "",
  specialization: "",
  qualification: "",
  registration_identifier: "",
  clinic_name: "",
  clinic_address: "",
  phone: "",
  languages: [],
};

export function draftFromAccount(d: DoctorAccount): DoctorDetailsDraft {
  return {
    name: d.name,
    specialization: d.specialization,
    qualification: d.qualification,
    registration_identifier: d.registration_identifier,
    clinic_name: d.clinic_name ?? "",
    clinic_address: d.clinic_address ?? "",
    phone: d.phone ?? "",
    languages: d.languages,
  };
}

export function detailsFromDraft(d: DoctorDetailsDraft): DoctorDetails {
  return {
    name: d.name.trim(),
    specialization: d.specialization.trim(),
    qualification: d.qualification.trim(),
    registration_identifier: d.registration_identifier.trim(),
    clinic_name: d.clinic_name.trim() || null,
    clinic_address: d.clinic_address.trim() || null,
    phone: d.phone.trim() || null,
    languages: d.languages,
  };
}

/** Every required detail filled in and at least one language chosen. */
export function isDraftComplete(d: DoctorDetailsDraft): boolean {
  const required = [d.name, d.specialization, d.qualification, d.registration_identifier];
  return required.every((v) => v.trim().length > 0) && d.languages.length > 0;
}

type TextKey = "name" | "specialization" | "qualification" | "registration_identifier" | "clinic_name" | "phone";

export function DoctorDetailsFields({
  value,
  onChange,
}: {
  value: DoctorDetailsDraft;
  onChange: (next: DoctorDetailsDraft) => void;
}) {
  const t = useT();
  const languagesId = useId();
  const set = <K extends keyof DoctorDetailsDraft>(key: K, next: DoctorDetailsDraft[K]) =>
    onChange({ ...value, [key]: next });

  const text = (
    key: TextKey,
    label: string,
    options: { hint?: string; maxLength: number; wide?: boolean; mono?: boolean } & Pick<
      InputHTMLAttributes<HTMLInputElement>,
      "autoComplete" | "required" | "type"
    >,
  ) => {
    const { hint, maxLength, wide, mono, ...input } = options;
    return (
      <Field label={label} hint={hint} className={cn(wide && "sm:col-span-2")}>
        {(p) => (
          <TextInput
            {...p}
            {...input}
            maxLength={maxLength}
            className={cn(mono && "font-mono tracking-wide")}
            value={value[key]}
            onChange={(e) => set(key, e.target.value)}
          />
        )}
      </Field>
    );
  };

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {text("name", t("doctorForm.name"), { maxLength: 120, autoComplete: "name", required: true, wide: true })}
      {text("specialization", t("doctorForm.specialization"), {
        hint: t("doctorForm.specializationHint"),
        maxLength: 120,
        required: true,
      })}
      {text("qualification", t("doctorForm.qualification"), {
        hint: t("doctorForm.qualificationHint"),
        maxLength: 200,
        required: true,
      })}
      {text("registration_identifier", t("doctorForm.registration"), {
        hint: t("doctorForm.registrationHint"),
        maxLength: 64,
        autoComplete: "off",
        required: true,
        wide: true,
        mono: true,
      })}
      {text("clinic_name", t("doctorForm.clinicName"), { maxLength: 200, autoComplete: "organization" })}
      {text("phone", t("doctorForm.phone"), { maxLength: 32, autoComplete: "tel", type: "tel" })}
      <Field label={t("doctorForm.clinicAddress")} className="sm:col-span-2">
        {(p) => (
          <TextArea
            {...p}
            rows={2}
            maxLength={1000}
            autoComplete="street-address"
            value={value.clinic_address}
            onChange={(e) => set("clinic_address", e.target.value)}
          />
        )}
      </Field>

      <div role="group" aria-labelledby={languagesId} className="sm:col-span-2">
        <p id={languagesId} className="text-sm font-semibold text-ink">
          {t("doctorForm.languages")}
        </p>
        <p className="mt-0.5 text-sm text-muted">{t("doctorForm.languagesHint")}</p>
        <ul className="mt-2.5 flex flex-wrap gap-2">
          {LANGUAGES.map((l) => {
            const on = value.languages.includes(l.code);
            return (
              <li key={l.code}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() =>
                    set("languages", on ? value.languages.filter((c) => c !== l.code) : [...value.languages, l.code])
                  }
                  className={cn(
                    "inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3.5 text-small font-medium transition-colors duration-150",
                    on
                      ? "border-brand bg-brand-soft text-brand-strong"
                      : "border-line-strong bg-surface text-muted hover:border-brand/40 hover:text-ink",
                  )}
                >
                  {on ? <Check size={14} weight="bold" aria-hidden /> : null}
                  {l.englishName}
                  {l.nativeName !== l.englishName ? (
                    <span lang={l.code} className={on ? "text-brand-strong/75" : "text-subtle"}>
                      {l.nativeName}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
