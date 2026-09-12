import { I18nProvider } from "@carebridge/i18n";
import { doctorCatalogs } from "@carebridge/i18n/catalogs";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";

export function renderWithI18n(ui: ReactNode) {
  return render(
    <I18nProvider locale="en" catalogs={doctorCatalogs}>
      {ui}
    </I18nProvider>,
  );
}
