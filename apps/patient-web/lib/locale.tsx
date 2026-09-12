"use client";

import { I18nProvider } from "@carebridge/i18n";
import { patientCatalogs } from "@carebridge/i18n/catalogs";
import { UI_LANGUAGES, isLanguageCode, type LanguageCode } from "@carebridge/shared-types";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

const STORAGE_KEY = "carebridge.patient.locale";
const DEFAULT_LOCALE: LanguageCode = UI_LANGUAGES[0];

interface LocaleControl {
  locale: LanguageCode;
  /** Explicit choice from the language switcher; remembered on this device. */
  setLocale: (code: LanguageCode) => void;
}

const LocaleContext = createContext<LocaleControl | null>(null);

function isUiLanguage(code: unknown): code is LanguageCode {
  return isLanguageCode(code) && UI_LANGUAGES.includes(code);
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LanguageCode>(DEFAULT_LOCALE);
  const explicit = useRef(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (isUiLanguage(stored)) {
        explicit.current = true;
        setLocaleState(stored);
      }
    } catch {
      /* storage unavailable */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((code: LanguageCode) => {
    if (!isUiLanguage(code)) return;
    explicit.current = true;
    setLocaleState(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* storage unavailable */
    }
  }, []);

  // The interface always starts in English and changes only when the person
  // using it asks (Phase 2 §2). The patient's preferred *medical* language is a
  // separate concept: it is shown to doctors and defaults the writing language.
  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return (
    <LocaleContext.Provider value={value}>
      <I18nProvider locale={locale} catalogs={patientCatalogs}>
        {children}
      </I18nProvider>
    </LocaleContext.Provider>
  );
}

export function useLocaleControl(): LocaleControl {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocaleControl must be used inside <LocaleProvider>");
  return ctx;
}
