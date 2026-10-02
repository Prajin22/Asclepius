/**
 * The facilitator's desk and the administrator's facilitator list (IP-SAKTI
 * Phase 3.5): designed screens with honest empty states. No escalation,
 * conversation, note or person is invented; the synthetic demo accounts appear
 * only in demo mode, labelled.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SAKTI_DEMO_ACCOUNTS } from "@/lib/demo";
import { renderSakti } from "@/test/utils";
import { DemoModeProvider } from "../SaktiShell";
import { BriefDesk, FacilitatorsAdmin, IncomingDesk, MessagesDesk, NotesDesk } from "./Desk";

const en = (key: string) => lookup(saktiCatalogs.en, key)!;
const RAW_KEY = /\b(desk|admin|pages|notAvailable|ui)\.[a-zA-Z]+/;
const SCREENS = [
  ["incoming", IncomingDesk, "desk.incoming.empty.title"],
  ["brief", BriefDesk, "desk.brief.empty.title"],
  ["messages", MessagesDesk, "desk.messages.select.title"],
  ["notes", NotesDesk, "desk.notes.empty.title"],
  ["facilitators", FacilitatorsAdmin, "admin.empty.title"],
] as const;

describe("the facilitator and administrator screens", () => {
  it.each(SCREENS)("%s shows its layout, an honest empty state, and that it is not available yet", (page, Screen, empty) => {
    renderSakti(<Screen />);
    expect(screen.getByRole("heading", { level: 1, name: en(`pages.${page}.title`) })).toBeInTheDocument();
    expect(screen.getByText(en(empty))).toBeInTheDocument();
    expect(screen.getAllByText(en("notAvailable.badge")).length).toBeGreaterThan(0);
  });

  it.each(SCREENS)("%s invents nothing and offers nothing to press", (_page, Screen) => {
    renderSakti(<Screen />);
    expect(screen.queryAllByRole("button")).toEqual([]);
    expect(screen.queryAllByRole("link")).toEqual([]);
    expect(document.querySelector("form, input, select, textarea")).toBeNull();
    expect(document.body.textContent).not.toMatch(/@/); // no addresses: no people
  });

  it("the incoming list has its columns but no rows", () => {
    renderSakti(<IncomingDesk />);
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(
      ["question", "product", "lanes", "received", "status"].map((c) => en(`desk.incoming.cols.${c}`)),
    );
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });

  it("names the synthetic demo accounts only in demo mode, and labels them", () => {
    renderSakti(
      <DemoModeProvider value>
        <FacilitatorsAdmin />
      </DemoModeProvider>,
    );
    expect(screen.getByText(en("admin.demo.body"))).toBeInTheDocument();
    expect(screen.getByText(en("ui.demo.tag"))).toBeInTheDocument();
    for (const account of SAKTI_DEMO_ACCOUNTS) expect(screen.getByText(account.email)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/@2026/); // never a password
  });

  it.each(SCREENS.flatMap(([page, Screen]) => ["hi", "ta"].map((locale) => [page, Screen, locale] as const)))(
    "%s renders entirely from the %s catalogue",
    (_page, Screen, locale) => {
      renderSakti(<Screen />, locale);
      expect(document.body.textContent).not.toMatch(RAW_KEY);
    },
  );
});
