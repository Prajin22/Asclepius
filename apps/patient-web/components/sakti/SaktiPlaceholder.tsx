"use client";

import { useT } from "@carebridge/i18n";
import { Card, EmptyState, PageHeader } from "@carebridge/ui";
import { Info } from "@phosphor-icons/react/dist/ssr";
import { SAKTI_PAGES, type SaktiPage } from "./nav";

/**
 * A screen that exists in the shell but not yet in the product.
 *
 * It says so plainly, says what the screen will do, and offers nothing to
 * press: no button, no field, no sample answer, no sample law. A placeholder
 * that looked as if it worked would be the one thing worse than none.
 */
export function SaktiPlaceholder({ page }: { page: SaktiPage }) {
  const t = useT();
  const info = SAKTI_PAGES[page];
  const headingId = `${page}-planned`;

  return (
    <>
      <PageHeader title={t(`pages.${page}.title`)} description={t(`pages.${page}.description`)} />
      <div className="flex max-w-3xl flex-col gap-5">
        <EmptyState title={t("notAvailable.title")}>{t("notAvailable.body")}</EmptyState>
        <Card aria-labelledby={headingId}>
          <h2 id={headingId} className="text-subheading text-ink">
            {t("notAvailable.whenReady")}
          </h2>
          <ul className="mt-3 flex list-disc flex-col gap-2 pl-5 text-muted marker:text-brand">
            {info.points.map((point) => (
              <li key={point}>{t(`pages.${page}.points.${point}`)}</li>
            ))}
          </ul>
          {info.note ? (
            <p className="mt-4 flex gap-2 border-t border-line pt-4 text-small text-muted">
              <Info size={17} aria-hidden className="mt-0.5 shrink-0 text-brand-strong" />
              {t(`pages.${page}.note`)}
            </p>
          ) : null}
        </Card>
      </div>
    </>
  );
}
