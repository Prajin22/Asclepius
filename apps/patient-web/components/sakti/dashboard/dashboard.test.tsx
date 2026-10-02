/**
 * The user's dashboard (IP-SAKTI Phase 3.5). Everything on it comes from the
 * API as it stands; what does not exist yet is listed as not ready, never shown
 * as working. The one demo action exists only in demo mode and adds a product
 * that is visibly synthetic.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import type { ClassificationSummary, ClassifierTree, ProductProfile } from "@carebridge/shared-types";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { DEMO_MARK, SAMPLE_PRODUCT } from "../classify/overview";
import { DemoModeProvider } from "../SaktiShell";
import { Dashboard } from "./Dashboard";

const h = vi.hoisted(() => ({
  api: {} as Record<string, Record<string, ReturnType<typeof vi.fn>>>,
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: h.push, replace: h.push }),
}));
vi.mock("@carebridge/api-client/react", async () => {
  const React = await import("react");
  return {
    useApi: () => h.api,
    useQuery: (fetcher: (api: unknown) => Promise<unknown>, deps: unknown[] = []) => {
      const [data, setData] = React.useState<unknown>(undefined);
      const [error, setError] = React.useState<unknown>(null);
      React.useEffect(() => {
        fetcher(h.api).then(setData, setError);
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, deps);
      return { data, error, loading: data === undefined, reload: vi.fn(), setData };
    },
  };
});

const en = (key: string) => lookup(saktiCatalogs.en, key)!;
const RAW_KEY = /\b(dashboard|ui|product|classifier)\.[a-zA-Z]+/;

const PRODUCT = {
  id: "pro-1", name: "Synthetic product", intended_use: null, dosage_form: null, administration_route: null,
  ingredients: [], preparation_method: null, classical_reference: null, extract_description: null,
  standardization_description: null, markers: [], notes: null, text_language: null, revision: 1,
  created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z", open_session_id: null,
  confirmed_classification: { session_id: "ses-2", outcome_id: "o", category: "cosmetic", tree_version: 1, decided_at: "2026-10-02T09:00:00Z" },
} as ProductProfile;

const HISTORY: ClassificationSummary[] = [
  { id: "ses-2", product_id: "pro-1", status: "user_confirmed", tree_version: 1, category: "cosmetic",
    created_at: "2026-10-02T08:00:00Z", decided_at: "2026-10-02T09:00:00Z", restarted_from_id: "ses-1" },
  { id: "ses-1", product_id: "pro-1", status: "superseded", tree_version: 1, category: null,
    created_at: "2026-10-01T08:00:00Z", decided_at: null, restarted_from_id: null },
];

const slot = (id: string, status: "verified" | "unverified" | "corpus_required") =>
  ({ id, lane: "india", describes_key: `classifier.v1.slot.${id}`, status, provision: null });
const TREE = { version: 1, nodes: [], slots: [slot("first_schedule", "corpus_required"), slot("category_cosmetic", "corpus_required")] } as unknown as ClassifierTree;

beforeEach(() => {
  h.push.mockReset();
  h.api = {
    products: {
      list: vi.fn(async () => [PRODUCT]),
      classifications: vi.fn(async () => HISTORY),
      create: vi.fn(async () => ({ ...PRODUCT, id: "pro-sample", name: SAMPLE_PRODUCT.name })),
    },
    classifier: { tree: vi.fn(async () => TREE) },
  };
});

describe("the dashboard", () => {
  it("leads with the product's purpose and three actions", async () => {
    renderSakti(<Dashboard />);
    expect(screen.getByRole("heading", { level: 1, name: en("dashboard.hero.title") })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: en("dashboard.actions.add") })[0]).toHaveAttribute("href", "/my-product/new");
    expect(screen.getAllByRole("link", { name: en("dashboard.actions.classify") })[0]).toHaveAttribute("href", "/classify");
    expect(screen.getByRole("link", { name: en("dashboard.actions.ask") })).toHaveAttribute("href", "/ask");
    await screen.findByRole("article", { name: "Synthetic product" });
  });

  it("lists readiness honestly: the answer engine and corpus are not ready", async () => {
    renderSakti(<Dashboard />);
    const ready = within(screen.getByRole("region", { name: en("dashboard.readiness.title") }));
    await ready.findByText(en("dashboard.readiness.answers"));
    const item = (label: string) => ready.getByText(label).closest("li")!;
    expect(item(en("dashboard.readiness.product")).textContent).toContain(en("ui.readiness.done"));
    expect(item(en("dashboard.readiness.classification")).textContent).toContain(en("ui.readiness.done"));
    expect(item(en("dashboard.readiness.corpus")).textContent).toContain(en("ui.readiness.notYet"));
    expect(item(en("dashboard.readiness.corpus")).textContent).toContain("0 of 2");
    expect(item(en("dashboard.readiness.answers")).textContent).toContain(en("ui.readiness.notYet"));
  });

  it("shows the most recent classification, and the reference counts", async () => {
    renderSakti(<Dashboard />);
    const recent = within(screen.getByRole("region", { name: en("dashboard.recent.title") }));
    expect(await recent.findByText(en("classifier.category.cosmetic"))).toBeInTheDocument();
    expect(recent.getByRole("link", { name: new RegExp(en("dashboard.recent.open")) })).toHaveAttribute("href", "/classify/ses-2");
    expect(recent.getByText(en("ui.infoOnly"))).toBeInTheDocument();
    const refs = within(screen.getByRole("region", { name: en("dashboard.references.title") }));
    const corpusRequired = (await refs.findByText(en("classifier.reference.corpus_required"))).closest("li")!;
    expect(corpusRequired.textContent).toContain("2");
  });

  it("guides a new user, and offers no sample outside demo mode", async () => {
    h.api.products.list = vi.fn(async () => []);
    renderSakti(<Dashboard />);
    expect(await screen.findByText(en("product.emptyTitle"))).toBeInTheDocument();
    expect(screen.getByText(en("dashboard.recent.empty"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: en("dashboard.start.title") })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en("ui.demo.loadSample") })).toBeNull();
  });

  it("in demo mode, adds one visibly synthetic sample when asked, and nothing legal", async () => {
    h.api.products.list = vi.fn(async () => []);
    renderSakti(
      <DemoModeProvider value>
        <Dashboard />
      </DemoModeProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: en("ui.demo.loadSample") }));
    expect(h.api.products.create).toHaveBeenCalledWith(SAMPLE_PRODUCT);
    expect(h.push).toHaveBeenCalledWith("/my-product/pro-sample");
    expect(SAMPLE_PRODUCT.name).toContain(DEMO_MARK);
    expect(SAMPLE_PRODUCT.classical_reference).toBeNull();
    expect(JSON.stringify(SAMPLE_PRODUCT)).not.toMatch(/\b(section|rule|article|schedule)\s+\w/i);
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", async (locale) => {
    renderSakti(<Dashboard />, locale);
    await screen.findByRole("article", { name: "Synthetic product" });
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});
