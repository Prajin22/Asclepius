"use client";

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

/**
 * Minimal, dependency-free localisation.
 *
 * Components call `t("section.key", { name })`. They never branch on a
 * language code — all language differences live in message catalogues and in
 * the INTL_LOCALES data table below.
 */

export type Messages = { [key: string]: string | Messages };
export type Catalogs = Record<string, Messages>;
export type Vars = Record<string, string | number>;
export type TFunction = (key: string, vars?: Vars) => string;

/** BCP-47 locale used for Intl formatting, per language code. Data, not logic. */
export const INTL_LOCALES: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  ta: "ta-IN",
  te: "te-IN",
  kn: "kn-IN",
  ml: "ml-IN",
  mr: "mr-IN",
  bn: "bn-IN",
  gu: "gu-IN",
  pa: "pa-IN",
  or: "or-IN",
  as: "as-IN",
};

export function lookup(messages: Messages | undefined, key: string): string | undefined {
  let node: string | Messages | undefined = messages;
  for (const part of key.split(".")) {
    if (node === undefined || typeof node === "string") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match,
  );
}

export function translate(catalogs: Catalogs, locale: string, fallbackLocale: string, key: string, vars?: Vars): string {
  const template = lookup(catalogs[locale], key) ?? lookup(catalogs[fallbackLocale], key);
  return template === undefined ? key : interpolate(template, vars);
}

export function mergeMessages(...parts: Messages[]): Messages {
  const out: Messages = {};
  for (const part of parts) {
    for (const [k, v] of Object.entries(part)) {
      const existing = out[k];
      out[k] =
        typeof v === "object" && typeof existing === "object" ? mergeMessages(existing, v) : v;
    }
  }
  return out;
}

/** Localised text for an error carrying a `code` (ApiError), falling back to errors.generic. */
export function errorMessage(t: TFunction, error: unknown): string {
  const code =
    typeof error === "object" && error !== null && typeof (error as { code?: unknown }).code === "string"
      ? (error as { code: string }).code
      : "generic";
  const key = `errors.${code}`;
  const text = t(key);
  return text === key ? t("errors.generic") : text;
}

/** All dotted keys in a catalogue (used by parity tests). */
export function flattenKeys(messages: Messages, prefix = ""): string[] {
  return Object.entries(messages).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : flattenKeys(v, `${prefix}${k}.`),
  );
}

interface I18nValue {
  locale: string;
  t: TFunction;
  formatDate: (iso: string | null | undefined) => string;
  formatDateTime: (iso: string | null | undefined) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  locale,
  catalogs,
  fallbackLocale = "en",
  children,
}: {
  locale: string;
  catalogs: Catalogs;
  fallbackLocale?: string;
  children: ReactNode;
}) {
  const t = useCallback<TFunction>(
    (key, vars) => translate(catalogs, locale, fallbackLocale, key, vars),
    [catalogs, locale, fallbackLocale],
  );
  const value = useMemo<I18nValue>(() => {
    const intl = INTL_LOCALES[locale] ?? INTL_LOCALES[fallbackLocale] ?? "en-IN";
    const date = new Intl.DateTimeFormat(intl, { day: "numeric", month: "short", year: "numeric" });
    const dateTime = new Intl.DateTimeFormat(intl, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
    const safe = (fmt: Intl.DateTimeFormat) => (iso: string | null | undefined) => {
      if (!iso) return "";
      const d = new Date(iso);
      return Number.isNaN(d.getTime()) ? "" : fmt.format(d);
    };
    return { locale, t, formatDate: safe(date), formatDateTime: safe(dateTime) };
  }, [locale, fallbackLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

export function useT(): TFunction {
  return useI18n().t;
}
