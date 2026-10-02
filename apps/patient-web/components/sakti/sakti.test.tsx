import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import { lookup } from "@carebridge/i18n";
import type { Role, SaktiRole } from "@carebridge/shared-types";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { SAKTI_NAV, SAKTI_PAGES, type SaktiPage } from "./nav";
import { SaktiLanding } from "./SaktiLanding";
import { SaktiPlaceholder } from "./SaktiPlaceholder";
import { SaktiShell } from "./SaktiShell";
import { SaktiSignIn } from "./SaktiSignIn";

const h = vi.hoisted(() => ({
  path: "/ask",
  replace: vi.fn(),
  logout: vi.fn(),
  login: vi.fn(),
  session: null as null | { user: { role: string; email: string } },
  apiProduct: "ip_sakti" as string,
  demo: false,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => h.path,
  useRouter: () => ({ replace: h.replace, push: h.replace }),
}));
vi.mock("@carebridge/api-client/react", () => ({
  useAuth: () => ({ session: h.session, ready: true, logout: h.logout, login: h.login }),
  useQuery: () => ({ data: { product: h.apiProduct, demo_mode: h.demo }, error: null, loading: false, reload: () => {} }),
}));
// The real switcher needs the app's LocaleProvider; its own behaviour is tested elsewhere.
vi.mock("@/components/LanguageSwitcher", () => ({ LanguageSwitcher: () => null }));

const en = (key: string) => lookup(saktiCatalogs.en, key)!;
const as = (role: Role) => ({ user: { role, email: `${role}@ipsakti.demo` } });

const MEDICAL = /patient|doctor|symptom|diagnos|prescri|medicat|medicine|allerg|clinic|hospital|health|consultation|treatment|emergency/i;
const RAW_KEY = /\b(nav|pages|notAvailable|disclaimer|role|areaLabel|signIn|landing|app|actions)\.[a-zA-Z]/;

beforeEach(() => {
  h.replace.mockReset();
  h.logout.mockReset();
  h.login.mockReset();
  h.session = null;
  h.path = "/ask";
  h.apiProduct = "ip_sakti";
  h.demo = false;
});

describe("the shell", () => {
  const roles = Object.keys(SAKTI_NAV) as SaktiRole[];

  it.each(roles)("shows %s its own destinations and nobody else's", (role) => {
    h.session = as(role);
    h.path = SAKTI_NAV[role][0].href;
    renderSakti(
      <SaktiShell role={role}>
        <p>content</p>
      </SaktiShell>,
    );
    for (const item of SAKTI_NAV[role]) expect(screen.getAllByText(en(item.label)).length).toBeGreaterThan(0);
    for (const other of roles.filter((r) => r !== role)) {
      for (const item of SAKTI_NAV[other]) {
        if (SAKTI_NAV[role].some((mine) => mine.label === item.label)) continue;
        expect(screen.queryByText(en(item.label))).toBeNull();
      }
    }
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it.each(roles)("carries the disclaimer and the prototype notice for %s", (role) => {
    h.session = as(role);
    renderSakti(<SaktiShell role={role}>x</SaktiShell>);
    expect(screen.getAllByText(en("disclaimer.short")).length).toBeGreaterThan(0);
    expect(screen.getByText(en("disclaimer.prototype"))).toBeInTheDocument();
  });

  it.each(roles)("never shows healthcare navigation or vocabulary to %s", (role) => {
    h.session = as(role);
    renderSakti(<SaktiShell role={role}>x</SaktiShell>);
    for (const healthcare of ["Home", "Health", "Documents", "Consultations", "Find Care", "Patients"]) {
      expect(screen.queryByRole("link", { name: healthcare })).toBeNull();
    }
    expect(document.body.textContent).not.toMatch(MEDICAL);
    expect(document.body.textContent).not.toMatch(/108|112/); // CareBridge's emergency line
  });

  it("marks where the person is", () => {
    h.session = as("curator");
    h.path = "/curator/upload";
    renderSakti(<SaktiShell role="curator">x</SaktiShell>);
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.every((link) => link.textContent?.includes(en("nav.upload")))).toBe(true);
  });

  it("sends someone in the wrong area to their own", () => {
    h.session = as("facilitator");
    renderSakti(<SaktiShell role="user">secret</SaktiShell>);
    expect(screen.queryByText("secret")).toBeNull();
    expect(h.replace).toHaveBeenCalledWith("/facilitator");
  });

  it("sends a signed-out visitor to sign in", () => {
    renderSakti(<SaktiShell role="user">secret</SaktiShell>);
    expect(screen.queryByText("secret")).toBeNull();
    expect(h.replace).toHaveBeenCalledWith("/login");
  });

  it("drops a CareBridge session rather than routing it anywhere", () => {
    h.session = as("patient");
    renderSakti(<SaktiShell role="user">secret</SaktiShell>);
    expect(screen.queryByText("secret")).toBeNull();
    expect(h.logout).toHaveBeenCalled();
    expect(h.replace).toHaveBeenCalledWith("/login");
  });

  it("marks a destination whose capability does not exist yet", () => {
    h.session = as("user");
    h.path = "/dashboard";
    renderSakti(<SaktiShell role="user">x</SaktiShell>);
    const ask = screen.getByRole("link", { name: new RegExp(en("nav.ask")) });
    expect(ask.textContent).toContain(en("nav.later"));
    const classify = screen.getByRole("link", { name: new RegExp(en("nav.classify")) });
    expect(classify.textContent).not.toContain(en("nav.later"));
  });

  it("lands a user on the dashboard", () => {
    expect(SAKTI_NAV.user[0].href).toBe("/dashboard");
  });

  it("opens the navigation in an accessible sheet from the menu button, and closes it on Escape", async () => {
    h.session = as("curator");
    h.path = "/curator";
    renderSakti(<SaktiShell role="curator">x</SaktiShell>);
    const menu = screen.getByRole("button", { name: en("ui.shell.openMenu") });
    expect(menu).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(menu);
    const dialog = screen.getByRole("dialog");
    for (const item of SAKTI_NAV.curator) expect(within(dialog).getByRole("link", { name: new RegExp(en(item.label)) })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows who is signed in, with their role, and signs out from the account menu", async () => {
    h.session = as("facilitator");
    h.path = "/facilitator";
    renderSakti(<SaktiShell role="facilitator">x</SaktiShell>);
    const account = screen.getByRole("button", { name: en("ui.user.menu") });
    await userEvent.click(account);
    expect(account).toHaveAttribute("aria-expanded", "true");
    const panel = within(document.getElementById(account.getAttribute("aria-controls")!)!);
    expect(panel.getByText("facilitator@ipsakti.demo")).toBeInTheDocument();
    expect(panel.getByText(en("role.facilitator"))).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(account).toHaveAttribute("aria-expanded", "false");
    expect(account).toHaveFocus();
    await userEvent.click(account);
    await userEvent.click(screen.getByRole("button", { name: new RegExp(en("actions.signOut")) }));
    expect(h.logout).toHaveBeenCalled();
  });

  it("marks demo mode on every screen, and explains exactly what is synthetic", async () => {
    h.session = as("user");
    h.demo = true;
    renderSakti(<SaktiShell role="user">x</SaktiShell>);
    await userEvent.click(screen.getByRole("button", { name: en("ui.demo.explain") }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText(en("ui.demo.points.never"))).toBeInTheDocument();
  });

  it("shows no demo marker outside demo mode", () => {
    h.session = as("user");
    renderSakti(<SaktiShell role="user">x</SaktiShell>);
    expect(screen.queryByRole("button", { name: en("ui.demo.explain") })).toBeNull();
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", (locale) => {
    h.session = as("user");
    renderSakti(<SaktiShell role="user">x</SaktiShell>, locale);
    for (const item of SAKTI_NAV.user) {
      expect(screen.getAllByText(lookup(saktiCatalogs[locale], item.label)!).length).toBeGreaterThan(0);
    }
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

describe("placeholders", () => {
  const all = Object.keys(SAKTI_PAGES) as SaktiPage[];
  const pages = all.filter((page) => !SAKTI_PAGES[page].available);

  it("every navigation destination has a page description", () => {
    const linked = new Set(Object.values(SAKTI_NAV).flatMap((items) => items.map((i) => i.page)));
    expect(linked).toEqual(new Set(all));
    for (const page of all) expect(lookup(saktiCatalogs.en, `pages.${page}.title`), page).toBeTruthy();
  });

  it("only the screens whose capability does not exist yet are placeholders", () => {
    expect(pages.sort()).toEqual(["ask", "brief", "escalate", "facilitators", "incoming", "messages", "notes"]);
  });

  it.each(pages)("%s says plainly that it is not available yet", (page) => {
    renderSakti(<SaktiPlaceholder page={page} />);
    expect(screen.getByRole("heading", { level: 1, name: en(`pages.${page}.title`) })).toBeInTheDocument();
    expect(screen.getAllByText(en("notAvailable.badge")).length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain(en("notAvailable.body"));
    for (const point of SAKTI_PAGES[page].points) {
      expect(screen.getByText(en(`pages.${page}.points.${point}`))).toBeInTheDocument();
    }
  });

  it.each(pages)("%s offers nothing to press, type into or follow", (page) => {
    renderSakti(<SaktiPlaceholder page={page} />);
    expect(screen.queryAllByRole("button")).toEqual([]);
    expect(screen.queryAllByRole("textbox")).toEqual([]);
    expect(screen.queryAllByRole("link")).toEqual([]);
    expect(document.querySelector("form, input, select, textarea")).toBeNull();
  });

  it.each(pages)("%s shows no law, no citation and no answer", (page) => {
    renderSakti(<SaktiPlaceholder page={page} />);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/\b(section|sec\.|rule|article|clause)\s+\d/i);
    expect(text).not.toMatch(/\bAct,?\s+(19|20)\d\d\b/);
    expect(text).not.toMatch(MEDICAL);
  });

  it.each(pages.flatMap((page) => ["hi", "ta"].map((locale) => [page, locale] as const)))(
    "%s renders in %s with no raw keys",
    (page, locale) => {
      renderSakti(<SaktiPlaceholder page={page} />, locale);
      expect(document.body.textContent).not.toMatch(RAW_KEY);
      expect(screen.getAllByText(lookup(saktiCatalogs[locale], "notAvailable.badge")!).length).toBeGreaterThan(0);
    },
  );

  it("shows a note where the screen has one", () => {
    renderSakti(<SaktiPlaceholder page="myProduct" />);
    expect(screen.getByText(en("pages.myProduct.note"))).toBeInTheDocument();
  });
});

describe("the landing page", () => {
  it("names the product, its domain, its status and its limits", () => {
    renderSakti(<SaktiLanding />);
    expect(screen.getByRole("heading", { level: 1, name: "IP-SAKTI Sahayak" })).toBeInTheDocument();
    expect(screen.getByText(en("app.domain"))).toBeInTheDocument();
    expect(screen.getByText(en("landing.status"))).toBeInTheDocument();
    expect(screen.getByText(en("disclaimer.short"))).toBeInTheDocument();
    expect(screen.getByText(en("disclaimer.prototype"))).toBeInTheDocument();
  });

  it("says exactly what works today and what does not, and links nowhere but sign-in", () => {
    renderSakti(<SaktiLanding />);
    expect(screen.getAllByText(en("landing.availability.available"))).toHaveLength(2);
    expect(screen.getAllByText(en("landing.availability.curators"))).toHaveLength(1);
    expect(screen.getAllByText(en("landing.availability.later"))).toHaveLength(2);
    expect(screen.getByText(en("landing.capabilities.answers.title"))).toBeInTheDocument();
    expect(screen.getByText(en("ui.infoOnly"))).toBeInTheDocument();
    for (const link of screen.getAllByRole("link")) expect(link).toHaveAttribute("href", "/login");
    expect(document.body.textContent).not.toMatch(MEDICAL);
    expect(document.body.textContent).not.toMatch(/government[- ]approved|official (service|app) of|certified|endorsed/i);
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", (locale) => {
    renderSakti(<SaktiLanding />, locale);
    expect(document.body.textContent).not.toMatch(RAW_KEY);
    expect(document.body.textContent).not.toMatch(/\b(ui|landing)\.[a-zA-Z]/);
  });
});

describe("signing in", () => {
  it("signs in and sends each role to its own area", async () => {
    h.login.mockResolvedValue(as("curator"));
    renderSakti(<SaktiSignIn />);
    await userEvent.type(screen.getByLabelText(en("signIn.email")), "curator@ipsakti.demo");
    await userEvent.type(screen.getByLabelText(en("signIn.password")), "Curator@2026");
    await userEvent.click(screen.getByRole("button", { name: en("actions.signIn") }));
    expect(h.login).toHaveBeenCalledWith("curator@ipsakti.demo", "Curator@2026");
    expect(h.replace).toHaveBeenCalledWith("/curator");
  });

  it("demo buttons only fill the form; they never sign in by themselves", async () => {
    renderSakti(<SaktiSignIn />);
    const demos = within(screen.getByRole("region", { name: en("signIn.demoTitle") }));
    await userEvent.click(demos.getByRole("button", { name: "Fill in as IP facilitator" }));
    expect(screen.getByLabelText(en("signIn.email"))).toHaveValue("facilitator@ipsakti.demo");
    expect(h.login).not.toHaveBeenCalled();
  });

  it("refuses a CareBridge account even if the server let it through", async () => {
    h.login.mockResolvedValue(as("doctor"));
    renderSakti(<SaktiSignIn />);
    await userEvent.type(screen.getByLabelText(en("signIn.email")), "meera@example.com");
    await userEvent.type(screen.getByLabelText(en("signIn.password")), "x");
    await userEvent.click(screen.getByRole("button", { name: en("actions.signIn") }));
    expect(h.logout).toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    expect(screen.getByText(en("errors.wrong_role"))).toBeInTheDocument();
  });

  it("says so when pointed at an API serving the other product", () => {
    h.apiProduct = "carebridge";
    renderSakti(<SaktiSignIn />);
    expect(screen.getByText(en("signIn.wrongProduct"))).toBeInTheDocument();
  });

  it("offers no sign-up and no role picker", () => {
    renderSakti(<SaktiSignIn />);
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByText(/create|register|sign up|apply/i)).toBeNull();
  });
});
