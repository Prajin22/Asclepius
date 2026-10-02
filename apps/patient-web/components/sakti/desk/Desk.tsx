"use client";

/**
 * The facilitator's desk and the administrator's facilitator list, designed
 * ahead of the phases that build them. Every screen shows its real layout with
 * a real empty state — no invented escalations, conversations, notes or people.
 * The only accounts named anywhere are the synthetic demo accounts, and only in
 * demo mode, labelled as such.
 */
import { useT } from "@carebridge/i18n";
import type { ReactNode } from "react";
import { BriefIcon, IncomingIcon, MessagesIcon, NotesIcon, PeopleIcon } from "@/components/icons";
import { SAKTI_DEMO_ACCOUNTS, SHOW_DEMO_ACCOUNT } from "@/lib/demo";
import { useDemoMode } from "../SaktiShell";
import { SaktiPlaceholder } from "../SaktiPlaceholder";
import { DemoTag, EmptyPanel } from "../ui";

/** A table that has its columns but no rows yet. Below md the header folds away. */
function EmptyTable({ caption, columns, children }: { caption: string; columns: string[]; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-surface">
      <table className="w-full text-left text-small">
        <caption className="sr-only">{caption}</caption>
        <thead className="hidden border-b border-line bg-sunken md:table-header-group">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-4 py-2.5 text-label uppercase text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={columns.length} className="p-4">
              {children}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function IncomingDesk() {
  const t = useT();
  return (
    <SaktiPlaceholder page="incoming">
      <EmptyTable
        caption={t("pages.incoming.title")}
        columns={["question", "product", "lanes", "received", "status"].map((c) => t(`desk.incoming.cols.${c}`))}
      >
        <EmptyPanel icon={IncomingIcon} title={t("desk.incoming.empty.title")} className="border-0 bg-transparent">
          {t("desk.incoming.empty.body")}
        </EmptyPanel>
      </EmptyTable>
    </SaktiPlaceholder>
  );
}

export function BriefDesk() {
  const t = useT();
  return (
    <SaktiPlaceholder page="brief">
      <EmptyPanel icon={BriefIcon} title={t("desk.brief.empty.title")}>
        {t("desk.brief.empty.body")}
      </EmptyPanel>
      <div className="grid gap-4 md:grid-cols-2">
        {(["question", "product", "supported", "notCovered"] as const).map((k) => (
          <section key={k} aria-labelledby={`brief-${k}`} className="rounded-md border border-line bg-surface p-5">
            <h2 id={`brief-${k}`} className="text-subheading text-ink">
              {t(`desk.brief.sections.${k}`)}
            </h2>
            <p className="mt-2 text-small text-subtle">{t("desk.brief.pending")}</p>
          </section>
        ))}
      </div>
    </SaktiPlaceholder>
  );
}

export function MessagesDesk() {
  const t = useT();
  return (
    <SaktiPlaceholder page="messages">
      <div className="grid overflow-hidden rounded-md border border-line bg-surface md:grid-cols-[18rem_minmax(0,1fr)]">
        <section aria-labelledby="conversations" className="border-b border-line md:border-b-0 md:border-r">
          <h2 id="conversations" className="border-b border-line px-4 py-3 text-small font-semibold text-ink">
            {t("desk.messages.list")}
          </h2>
          <p className="px-4 py-6 text-small text-muted">{t("desk.messages.empty")}</p>
        </section>
        <div className="flex flex-col">
          <EmptyPanel icon={MessagesIcon} title={t("desk.messages.select.title")} className="m-4 flex-1">
            {t("desk.messages.select.body")}
          </EmptyPanel>
          <p className="mx-4 mb-4 rounded-md border border-dashed border-line-strong/60 px-4 py-3 text-small text-muted">
            {t("desk.messages.reply")}
          </p>
        </div>
      </div>
    </SaktiPlaceholder>
  );
}

export function NotesDesk() {
  const t = useT();
  return (
    <SaktiPlaceholder page="notes">
      <EmptyPanel icon={NotesIcon} title={t("desk.notes.empty.title")}>
        {t("desk.notes.empty.body")}
      </EmptyPanel>
    </SaktiPlaceholder>
  );
}

export function FacilitatorsAdmin() {
  const t = useT();
  const demo = useDemoMode();
  return (
    <SaktiPlaceholder page="facilitators">
      <EmptyTable
        caption={t("pages.facilitators.title")}
        columns={["name", "email", "role", "status", "activity"].map((c) => t(`admin.cols.${c}`))}
      >
        <EmptyPanel icon={PeopleIcon} title={t("admin.empty.title")} className="border-0 bg-transparent">
          {t("admin.empty.body")}
        </EmptyPanel>
      </EmptyTable>
      {demo && SHOW_DEMO_ACCOUNT ? (
        <section aria-labelledby="demo-accounts" className="rounded-md border border-dashed border-demo/50 bg-surface p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="demo-accounts" className="text-subheading text-ink">
              {t("admin.demo.title")}
            </h2>
            <DemoTag />
          </div>
          <p className="mt-1 text-small text-muted">{t("admin.demo.body")}</p>
          <ul className="mt-4 divide-y divide-line rounded-md border border-line">
            {SAKTI_DEMO_ACCOUNTS.map((a) => (
              <li key={a.email} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
                <span className="font-medium text-ink">{t(`role.${a.role}`)}</span>
                <code className="text-small text-muted">{a.email}</code>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </SaktiPlaceholder>
  );
}
