import { Select, type ControlProps } from "@carebridge/ui";
import { LANGUAGES, type LanguageCode } from "@carebridge/shared-types";

/** Any of the registered languages (content language, not UI language). */
export function LanguageSelect({
  value,
  onChange,
  emptyLabel,
  ...control
}: ControlProps & {
  value: LanguageCode | "";
  onChange: (value: LanguageCode | "") => void;
  emptyLabel?: string;
}) {
  return (
    <Select {...control} value={value} onChange={(e) => onChange(e.target.value as LanguageCode | "")}>
      {emptyLabel !== undefined ? <option value="">{emptyLabel}</option> : null}
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code} lang={l.code}>
          {l.nativeName}
        </option>
      ))}
    </Select>
  );
}
