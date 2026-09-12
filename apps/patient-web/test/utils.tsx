import { I18nProvider } from "@carebridge/i18n";
import { patientCatalogs } from "@carebridge/i18n/catalogs";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";

export function renderWithI18n(ui: ReactNode, locale = "en") {
  return render(
    <I18nProvider locale={locale} catalogs={patientCatalogs}>
      {ui}
    </I18nProvider>,
  );
}
