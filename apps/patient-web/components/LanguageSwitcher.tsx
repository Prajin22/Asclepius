"use client";

import { useT } from "@carebridge/i18n";
import { UI_LANGUAGES, languageInfo, type LanguageCode } from "@carebridge/shared-types";
import { useId } from "react";
import { useLocaleControl } from "@/lib/locale";

/** Switches the interface language. Options are shown in their own script. */
export function LanguageSwitcher() {
  const t = useT();
  const { locale, setLocale } = useLocaleControl();
  const id = useId();
  return (
    <div className="flex items-center">
      <label htmlFor={id} className="sr-only">
        {t("language.switcher")}
      </label>
      <select
        id={id}
        value={locale}
        onChange={(e) => setLocale(e.target.value as LanguageCode)}
        className="min-h-11 rounded-md border border-line-strong bg-surface px-2.5 text-small font-medium text-ink sm:min-h-10"
      >
        {UI_LANGUAGES.map((code) => (
          <option key={code} value={code} lang={code}>
            {languageInfo(code)?.nativeName}
          </option>
        ))}
      </select>
    </div>
  );
}
