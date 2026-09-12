import type { TFunction } from "@carebridge/i18n";

export function formatBytes(bytes: number, t: TFunction): string {
  if (bytes < 1024 * 1024) return t("units.kb", { n: Math.max(1, Math.round(bytes / 1024)) });
  return t("units.mb", { n: (bytes / (1024 * 1024)).toFixed(1) });
}
