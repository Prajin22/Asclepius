import type { TFunction } from "@carebridge/i18n";
import { languageInfo, type PatientIdentity } from "@carebridge/shared-types";

/** "46 y · Male · prefers Tamil (தமிழ்)" */
export function patientMeta(p: PatientIdentity, t: TFunction): string {
  const info = languageInfo(p.preferred_language);
  const language = info ? `${info.englishName} (${info.nativeName})` : p.preferred_language;
  return t("dashboard.patientMeta", {
    age: p.age !== null ? t("dashboard.ageYears", { age: p.age }) : t("dashboard.ageUnknown"),
    sex: t(`sex.${p.sex}`),
    language,
  });
}

export function languageLabel(code: string | null | undefined): string {
  const info = languageInfo(code as never);
  return info ? `${info.englishName} (${info.nativeName})` : "";
}
