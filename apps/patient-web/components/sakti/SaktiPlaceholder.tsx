"use client";

import { useT } from "@carebridge/i18n";
import { Badge, PageHeader } from "@carebridge/ui";
import { Clock, Info } from "@phosphor-icons/react/dist/ssr";
import type { ReactNode } from "react";
import { SAKTI_PAGES, type SaktiPage } from "./nav";
import { LaterRelease } from "./ui";

/**
 * A screen whose capability does not exist yet.
 *
 * It says so plainly, says what the screen will do, and offers nothing to
 * press: no working button, no sample answer, no sample law, no invented
 * conversation. `children` is the screen's designed empty layout, if it has
 * one. A placeholder that looked as if it worked would be worse than none.
 */
export function SaktiPlaceholder({ page, children }: { page: SaktiPage; children?: ReactNode }) {
  const t = useT();
  const info = SAKTI_PAGES[page];

  return (
    <>
      <PageHeader
        title={t(`pages.${page}.title`)}
        description={t(`pages.${page}.description`)}
        actions={
          <Badge tone="neutral">
            <Clock size={13} weight="bold" aria-hidden />
            {t("notAvailable.badge")}
          </Badge>
        }
      />
      <div className="flex flex-col gap-5">
        {children}
        <LaterRelease
          title={t("notAvailable.title")}
          body={`${t("notAvailable.body")} ${t("notAvailable.whenReady")}`}
          points={info.points.map((point) => t(`pages.${page}.points.${point}`))}
        />
        {info.note ? (
          <p className="flex gap-2 text-small text-muted">
            <Info size={17} aria-hidden className="mt-0.5 shrink-0 text-brand-strong" />
            {t(`pages.${page}.note`)}
          </p>
        ) : null}
      </div>
    </>
  );
}
