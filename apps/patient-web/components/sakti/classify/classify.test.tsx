/**
 * The Classify and My Products screens (IP-SAKTI Phase 3, redesigned in 3.5).
 *
 * The screens decide nothing: questions, order and result come from the API.
 * What is tested is that they show it faithfully — a guided step at a time,
 * "I don't know" always on offer and set apart, a hard stop that says what is
 * missing and suggests no category, a result shown as the classifier's and
 * awaiting the user's own confirmation, a read-only history, a product editor
 * with no field for a conclusion — and that all of it renders in English,
 * Hindi and Tamil.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import type {
  ClassificationSession,
  ClassificationSummary,
  ClassifierSlot,
  ClassifierTree,
  ProductProfile,
} from "@carebridge/shared-types";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { ClassificationFlow } from "./ClassificationFlow";
import { MyProducts } from "./MyProducts";
import { productState } from "./overview";
import { ProductDetail } from "./ProductDetail";
import { ProductEditor } from "./ProductEditor";
import { ReferenceList } from "./ReferenceList";
import { ClassificationTimeline } from "./status";

const h = vi.hoisted(() => ({
  api: {} as Record<string, Record<string, ReturnType<typeof vi.fn>>>,
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/classify",
  useRouter: () => ({ push: h.push, replace: h.push }),
  useParams: () => ({ id: "ses-1" }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@carebridge/api-client/react", async () => {
  const React = await import("react");
  return {
    useApi: () => h.api,
    useAuth: () => ({ session: null, ready: true, logout: vi.fn(), login: vi.fn() }),
    useQuery: (fetcher: (api: unknown) => Promise<unknown>, deps: unknown[] = []) => {
      const [data, setData] = React.useState<unknown>(undefined);
      const [error, setError] = React.useState<unknown>(null);
      const [tick, setTick] = React.useState(0);
      React.useEffect(() => {
        let live = true;
        fetcher(h.api).then(
          (value) => live && setData(value),
          (err) => live && setError(err),
        );
        return () => {
          live = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, [...deps, tick]);
      return { data, error, loading: data === undefined, reload: () => setTick((n) => n + 1), setData };
    },
  };
});

const en = (key: string) => lookup(saktiCatalogs.en, key)!;
const MEDICAL = /patient|doctor|symptom|diagnos|prescri|medicat|medicine|allerg|clinic|hospital|health|consultation|treatment|disease|emergency/i;
const RAW_KEY = /\b(classifier|product|pages|errors|ui)\.[a-zA-Z0-9_]+\.[a-zA-Z]/;
const OUTCOME_ID = "out-1";

const node = (id: string, choices: string[], context: string[] = [], references: string[] = []) => ({
  id,
  question_key: `classifier.v1.${id}.question`,
  help_key: `classifier.v1.${id}.help`,
  missing_key: `classifier.v1.${id}.missing`,
  why_key: `classifier.v1.${id}.why`,
  choices: [...choices, "unknown"].map((c) => ({ id: c, label_key: `classifier.choice.${c}` })),
  context_fields: context,
  references,
});

const slot = (id: string, status: ClassifierSlot["status"] = "corpus_required"): ClassifierSlot => ({
  id,
  lane: "india",
  describes_key: `classifier.v1.slot.${id}`,
  status,
  provision: null,
});

const TREE: ClassifierTree = {
  classifier_id: "ip_sakti_formulation", version: 1, fingerprint: "f", current: true, status: "engineering_draft",
  legal_review: "required", start: "purpose",
  nodes: [
    node("purpose", ["therapeutic", "nutrition", "external_beautification"], ["intended_use", "dosage_form"]),
    node("classical_formula", ["yes", "no"], ["classical_reference", "ingredients"], ["first_schedule"]),
    node("schedule_combination", ["yes", "no"], ["ingredients", "administration_route"], ["first_schedule"]),
    node("phytopharmaceutical", ["yes", "no"], ["markers"]),
  ],
  categories: ["ayurveda_aahara", "cosmetic", "classical", "patent_proprietary", "phytopharmaceutical", "new_or_non_classical"],
  slots: [slot("first_schedule"), slot("category_classical")],
};

function session(overrides: Partial<ClassificationSession> = {}): ClassificationSession {
  return {
    id: "ses-1", product_id: "pro-1", status: "incomplete", tree_version: 1, category: null,
    created_at: "2026-10-01T08:00:00Z", decided_at: null, restarted_from_id: null, product_name: "Synthetic product",
    classifier_id: "ip_sakti_formulation", tree_fingerprint: "f", current_node_id: "purpose", path: [],
    latest_outcome: null, outcomes: [], answer_history: [], references: [], product_revision: 1,
    product_snapshot: { intended_use: "Daily use", dosage_form: null, ingredients: [{ name: "Ingredient A" }],
      administration_route: "oral", markers: [] },
    decided_outcome_id: null, rejection_reason: null, updated_at: "2026-10-01T08:00:00Z",
    ...overrides,
  };
}

const determined = (category: ClassificationSession["category"], overrides: Partial<ClassificationSession> = {}) => {
  const outcome = {
    id: OUTCOME_ID, sequence: 1, kind: "determined" as const, category, stop_node_id: null,
    path: [{ node_id: "purpose", choice: "therapeutic" }, { node_id: "classical_formula", choice: "yes" }],
    answers_sha256: "a", tree_version: 1, references: [], created_at: "2026-10-01T08:05:00Z",
  };
  return session({
    status: "determined", category, current_node_id: null, path: outcome.path, latest_outcome: outcome,
    outcomes: [outcome], references: [slot("first_schedule"), slot("category_classical")], ...overrides,
  });
};

const PRODUCT = {
  id: "pro-1", name: "Synthetic product", intended_use: "Synthetic purpose", dosage_form: "Tablet", administration_route: "oral",
  ingredients: [{ name: "Ingredient A", part_used: null, quantity: null }], preparation_method: null, classical_reference: null,
  extract_description: null, standardization_description: null, markers: [], notes: null, text_language: null, revision: 2,
  created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z", open_session_id: null, confirmed_classification: null,
} as ProductProfile;

const summary = (overrides: Partial<ClassificationSummary> = {}): ClassificationSummary => ({
  id: "ses-1", product_id: "pro-1", status: "incomplete", tree_version: 1, category: null,
  created_at: "2026-10-01T08:00:00Z", decided_at: null, restarted_from_id: null, ...overrides,
});

beforeEach(() => {
  h.push.mockReset();
  h.api = {
    classifier: {
      session: vi.fn(async () => session()),
      tree: vi.fn(async () => TREE),
      respond: vi.fn(async () => session()),
      confirm: vi.fn(async () => determined("classical", { status: "user_confirmed", decided_at: "2026-10-01T09:00:00Z" })),
      reject: vi.fn(async () => determined("classical", { status: "user_rejected", decided_at: "2026-10-01T09:00:00Z" })),
      restart: vi.fn(async () => session({ id: "ses-2", restarted_from_id: "ses-1" })),
      start: vi.fn(async () => session({ id: "ses-new" })),
    },
    products: {
      list: vi.fn(async () => []),
      get: vi.fn(async () => PRODUCT),
      classifications: vi.fn(async () => []),
      create: vi.fn(async (values: unknown) => ({ ...PRODUCT, id: "pro-new", ...(values as object) })),
      update: vi.fn(),
    },
  };
});

// --------------------------------------------------------------------------
// The questions
// --------------------------------------------------------------------------

describe("answering", () => {
  it("asks one question as step 1 of 4, always offers 'I don't know', and sends only a choice id", async () => {
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByText(en("classifier.v1.purpose.question"))).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByLabelText(new RegExp(en("classifier.choice.unknown")))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.flow.unknownHint"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.v1.purpose.hint.nutrition"))).toBeInTheDocument();
    expect(screen.getByText("Daily use")).toBeInTheDocument(); // the user's own description, shown back
    await userEvent.click(screen.getByLabelText(new RegExp(en("classifier.choice.nutrition"))));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.continue") }));
    expect(h.api.classifier.respond).toHaveBeenCalledWith("ses-1", "purpose", "nutrition");
  });

  it("will not continue without a choice", async () => {
    renderSakti(<ClassificationFlow id="ses-1" />);
    await screen.findByText(en("classifier.v1.purpose.question"));
    expect(screen.getByRole("button", { name: en("classifier.session.continue") })).toBeDisabled();
  });

  it("shows no question the tree has not reached", async () => {
    renderSakti(<ClassificationFlow id="ses-1" />);
    await screen.findByText(en("classifier.v1.purpose.question"));
    for (const later of ["classical_formula", "schedule_combination", "phytopharmaceutical"]) {
      expect(screen.queryByText(en(`classifier.v1.${later}.question`))).toBeNull();
    }
  });

  it("goes Back by reopening the previous answer, already chosen, to change it", async () => {
    h.api.classifier.session = vi.fn(async () =>
      session({ current_node_id: "classical_formula", path: [{ node_id: "purpose", choice: "therapeutic" }] }),
    );
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByText("Step 2 of 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: en("classifier.flow.back") }));
    expect(screen.getByText(en("classifier.v1.purpose.question"))).toBeInTheDocument();
    expect(screen.getByLabelText(new RegExp(en("classifier.choice.therapeutic")))).toBeChecked();
    await userEvent.click(screen.getByLabelText(new RegExp(en("classifier.choice.external_beautification"))));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.continue") }));
    expect(h.api.classifier.respond).toHaveBeenCalledWith("ses-1", "purpose", "external_beautification");
  });

  it("lets an earlier answer be changed from the list of answers", async () => {
    h.api.classifier.session = vi.fn(async () =>
      session({ current_node_id: "classical_formula", path: [{ node_id: "purpose", choice: "therapeutic" }] }),
    );
    renderSakti(<ClassificationFlow id="ses-1" />);
    const answers = within(await screen.findByRole("region", { name: en("classifier.session.answered") }));
    expect(answers.getByText(en("classifier.v1.purpose.short"))).toBeInTheDocument();
    await userEvent.click(answers.getByRole("button", { name: new RegExp(en("classifier.session.change")) }));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.cancelChange") }));
    expect(screen.getByText(en("classifier.v1.classical_formula.question"))).toBeInTheDocument();
  });
});

describe("an unknown answer", () => {
  it("stops, says what is missing and why, assumes nothing, and suggests no category", async () => {
    h.api.classifier.session = vi.fn(async () =>
      session({
        status: "requires_information", current_node_id: "schedule_combination",
        path: [
          { node_id: "purpose", choice: "therapeutic" },
          { node_id: "classical_formula", choice: "no" },
          { node_id: "schedule_combination", choice: "unknown" },
        ],
      }),
    );
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByRole("heading", { name: en("classifier.unknown.title") })).toBeInTheDocument();
    expect(screen.getByText(en("classifier.v1.schedule_combination.missing"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.v1.schedule_combination.why"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.unknown.assumed"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en("classifier.unknown.review") })).toHaveAttribute("href", "/my-product/pro-1/edit");
    expect(screen.getByRole("link", { name: en("classifier.unknown.return") })).toHaveAttribute("href", "/my-product/pro-1");
    for (const category of TREE.categories) expect(screen.queryByText(en(`classifier.category.${category}`))).toBeNull();
    expect(screen.queryByRole("button", { name: en("classifier.session.confirm") })).toBeNull();
    expect(document.body.textContent).not.toMatch(/likely|probably|best match|estimated|suggest/i);
  });

  it("can change the unknown answer in place", async () => {
    h.api.classifier.session = vi.fn(async () =>
      session({ status: "requires_information", current_node_id: "purpose", path: [{ node_id: "purpose", choice: "unknown" }] }),
    );
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.unknown.change") }));
    await userEvent.click(screen.getByLabelText(new RegExp(en("classifier.choice.nutrition"))));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.continue") }));
    expect(h.api.classifier.respond).toHaveBeenCalledWith("ses-1", "purpose", "nutrition");
  });
});

// --------------------------------------------------------------------------
// The result
// --------------------------------------------------------------------------

describe("a result", () => {
  it("is the classifier's proposal, explained, awaiting confirmation, with each reference's status", async () => {
    h.api.classifier.session = vi.fn(async () => determined("classical"));
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByText(en("classifier.category.classical"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.result.complete"))).toBeInTheDocument();
    expect(screen.getAllByText(en("classifier.result.determined")).length).toBeGreaterThan(0);
    expect(screen.getByText(en("classifier.result.allAnswered"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.session.awaiting"))).toBeInTheDocument();
    expect(screen.getAllByText(en("classifier.reference.corpus_required"))).toHaveLength(2);
    expect(screen.getByText(en("classifier.session.resultNote"))).toBeInTheDocument();
    expect(screen.getByText(en("ui.infoOnly"))).toBeInTheDocument();
    const how = within(screen.getByRole("region", { name: en("classifier.result.how") }));
    expect(how.getByText(en("classifier.v1.classical_formula.short"))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/legally classified|is approved|can legally sell|compliant/i);
  });

  it("is confirmed only by an explicit action naming the result shown", async () => {
    h.api.classifier.session = vi.fn(async () => determined("classical"));
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.session.confirm") }));
    expect(h.api.classifier.confirm).toHaveBeenCalledWith("ses-1", OUTCOME_ID);
    expect(await screen.findByText(/Confirmed by you on/)).toBeInTheDocument();
  });

  it("offers ways to change something, and rejecting puts nothing in its place", async () => {
    h.api.classifier.session = vi.fn(async () => determined("cosmetic"));
    h.api.classifier.reject = vi.fn(async () => determined("cosmetic", { status: "user_rejected", decided_at: "2026-10-01T09:00:00Z" }));
    renderSakti(<ClassificationFlow id="ses-1" />);
    const change = await screen.findByRole("button", { name: en("classifier.result.change") });
    await userEvent.click(change);
    expect(change).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: en("classifier.result.editProduct") })).toHaveAttribute("href", "/my-product/pro-1/edit");
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.reject") }));
    expect(screen.getByText(en("classifier.result.rejectNote"))).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(en("classifier.session.rejectReason")), "It is not for beautification");
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.confirmReject") }));
    expect(h.api.classifier.reject).toHaveBeenCalledWith("ses-1", OUTCOME_ID, "It is not for beautification");
    expect(await screen.findByText(en("classifier.session.rejectedNote"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en("classifier.session.confirm") })).toBeNull();
  });

  it("starts again as a new classification", async () => {
    h.api.classifier.session = vi.fn(async () => determined("classical", { status: "user_rejected", decided_at: "2026-10-01T09:00:00Z" }));
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.session.restart") }));
    await waitFor(() => expect(h.push).toHaveBeenCalledWith("/classify/ses-2"));
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", async (locale) => {
    h.api.classifier.session = vi.fn(async () => determined("phytopharmaceutical"));
    renderSakti(<ClassificationFlow id="ses-1" />, locale);
    await screen.findByText(lookup(saktiCatalogs[locale], "classifier.category.phytopharmaceutical")!);
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });

  it.each(["hi", "ta"])("renders a question entirely from the %s catalogue", async (locale) => {
    renderSakti(<ClassificationFlow id="ses-1" />, locale);
    await screen.findByText(lookup(saktiCatalogs[locale], "classifier.v1.purpose.question")!);
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

describe("references", () => {
  it("never presents an unverified or missing reference as a citation", () => {
    renderSakti(<ReferenceList slots={[slot("first_schedule"), { ...slot("category_classical"), status: "unverified" }]} />);
    expect(screen.getByText(en("classifier.reference.corpusRequiredNote"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.reference.unverifiedNote"))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\b(section|rule|article)\s+\d/i);
  });

  it("names a verified source by its stored metadata only", () => {
    renderSakti(
      <ReferenceList
        slots={[{
          ...slot("first_schedule", "verified"),
          provision: {
            provision_version_id: "pv", locator: "Synthetic locator", version_number: 2,
            instrument_title: "Synthetic instrument", source_title: "Synthetic source", source_authority: "india_code",
          },
        }]}
      />,
    );
    expect(screen.getByText("Synthetic instrument · Synthetic locator · version 2 · Synthetic source")).toBeInTheDocument();
    expect(screen.getByText(en("classifier.reference.verified"))).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------------
// History
// --------------------------------------------------------------------------

describe("classification history", () => {
  const history = [
    summary({ id: "ses-3", status: "incomplete", created_at: "2026-10-03T08:00:00Z", restarted_from_id: "ses-2" }),
    summary({ id: "ses-2", status: "user_confirmed", category: "classical", decided_at: "2026-10-02T09:00:00Z", created_at: "2026-10-02T08:00:00Z" }),
    summary({ id: "ses-1", status: "requires_information", created_at: "2026-10-01T08:00:00Z" }),
  ];

  it("lists every session newest first, numbered, with its version, result, confirmation and restarts", () => {
    renderSakti(<ClassificationTimeline history={history} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0]).getByText("Classification 3")).toBeInTheDocument();
    expect(within(items[0]).getByText(en("classifier.timeline.restart"))).toBeInTheDocument();
    expect(within(items[1]).getByText(en("classifier.category.classical"))).toBeInTheDocument();
    expect(within(items[1]).getByText(en("classifier.timeline.confirmed"))).toBeInTheDocument();
    expect(within(items[2]).getByText(en("classifier.timeline.noCategory"))).toBeInTheDocument();
    expect(within(items[2]).getByText(en("classifier.status.requires_information"))).toBeInTheDocument();
    expect(screen.getAllByText(en("classifier.timeline.version"))).toHaveLength(3);
  });

  it("is read-only: it only links to each session", () => {
    renderSakti(<ClassificationTimeline history={history} />);
    expect(screen.queryAllByRole("button")).toEqual([]);
    expect(screen.getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/classify/ses-3", "/classify/ses-2", "/classify/ses-1"]);
  });

  it("says when there is none", () => {
    renderSakti(<ClassificationTimeline history={[]} />);
    expect(screen.getByText(en("classifier.timeline.empty"))).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------------
// Products
// --------------------------------------------------------------------------

describe("a product's classification state", () => {
  it("is derived from the open session, then the confirmation, and nothing else", () => {
    const open = { ...PRODUCT, open_session_id: "ses-1" };
    expect(productState(PRODUCT, [])).toBe("not_classified");
    expect(productState(open, [summary({ status: "incomplete" })])).toBe("in_progress");
    expect(productState(open, [summary({ status: "requires_information" })])).toBe("requires_information");
    expect(productState(open, [summary({ status: "determined" })])).toBe("awaiting_confirmation");
    const confirmed = { ...PRODUCT, confirmed_classification: { session_id: "s", outcome_id: "o", category: "classical" as const, tree_version: 1, decided_at: "x" } };
    expect(productState(confirmed, [])).toBe("confirmed");
    // A rejected result leaves the product unclassified.
    expect(productState(PRODUCT, [summary({ status: "user_rejected", category: "cosmetic" })])).toBe("not_classified");
  });
});

describe("the product editor", () => {
  it("has fields for the user's own description and none for a conclusion", async () => {
    renderSakti(<ProductEditor onSubmit={vi.fn()} />);
    expect(screen.getByText(en("product.factsNote"))).toBeInTheDocument();
    for (const key of ["preparation", "classical", "extract", "markers", "notes"]) {
      await userEvent.click(screen.getByRole("button", { name: en(`product.section.${key}.title`) }));
    }
    const labels = Array.from(document.querySelectorAll("label")).map((l) => l.textContent ?? "").join(" ");
    expect(labels).not.toMatch(/categor|classif|schedule|approved|legal/i);
  });

  it("shows the nine sections, the essentials open and the rest on request", async () => {
    renderSakti(<ProductEditor onSubmit={vi.fn()} />);
    expect(screen.getAllByRole("region")).toHaveLength(9);
    expect(screen.getByLabelText(new RegExp(en("product.field.name")))).toBeInTheDocument();
    expect(screen.queryByLabelText(en("product.field.preparation_method"))).toBeNull();
    const toggle = screen.getByRole("button", { name: en("product.section.preparation.title") });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText(en("product.field.preparation_method"))).toBeInTheDocument();
    // Only the identity section, which holds the name, is required.
    const identity = screen.getByRole("region", { name: new RegExp(en("product.section.identity.title")) });
    for (const tag of screen.getAllByText(en("ui.required"))) expect(identity.contains(tag)).toBe(true);
  });

  it("requires a name, says so inline, and saves nothing until it has one", async () => {
    const onSubmit = vi.fn(async () => undefined);
    renderSakti(<ProductEditor onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: en("product.create") }));
    expect(screen.getByText(en("product.validation.name"))).toBeInTheDocument();
    expect(screen.getByLabelText(new RegExp(en("product.field.name")))).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("marks unsaved changes and saves what was written, without blanks", async () => {
    const onSubmit = vi.fn(async () => undefined);
    renderSakti(<ProductEditor onSubmit={onSubmit} />);
    expect(screen.getByText(en("product.nothingYet"))).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(new RegExp(en("product.field.name"))), "Synthetic product");
    expect(screen.getByText(en("product.unsaved"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: en("product.ingredient.add") }));
    await userEvent.type(screen.getByLabelText(en("product.ingredient.name")), "Ingredient A");
    await userEvent.click(screen.getByRole("button", { name: en("product.create") }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Synthetic product",
        ingredients: [{ name: "Ingredient A", part_used: null, quantity: null }],
        markers: [],
        intended_use: null,
      }),
      "view",
    );
  });

  it("will not silently drop an ingredient that has a quantity but no name", async () => {
    const onSubmit = vi.fn(async () => undefined);
    renderSakti(<ProductEditor onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(new RegExp(en("product.field.name"))), "Synthetic product");
    await userEvent.click(screen.getByRole("button", { name: en("product.ingredient.add") }));
    await userEvent.type(screen.getByLabelText(en("product.ingredient.quantity")), "10 g");
    await userEvent.click(screen.getByRole("button", { name: en("product.create") }));
    expect(screen.getByText(en("product.validation.ingredient"))).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("can save and go straight on to classify", async () => {
    const onSubmit = vi.fn(async () => undefined);
    renderSakti(<ProductEditor onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(new RegExp(en("product.field.name"))), "Synthetic product");
    await userEvent.click(screen.getByRole("button", { name: en("product.createAndClassify") }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: "Synthetic product" }), "classify");
  });

  it("opens an existing product's filled sections, and saves only a change", async () => {
    const product = { ...PRODUCT, notes: "Synthetic note" };
    renderSakti(<ProductEditor product={product} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(en("product.field.notes"))).toHaveValue("Synthetic note");
    expect(screen.queryByLabelText(en("product.field.preparation_method"))).toBeNull();
    expect(screen.getByRole("button", { name: en("product.save") })).toBeDisabled();
  });
});

describe("My Products", () => {
  const confirmed = {
    ...PRODUCT,
    confirmed_classification: { session_id: "s", outcome_id: "o", category: "classical" as const, tree_version: 1, decided_at: "x" },
  };
  const inProgress = { ...PRODUCT, id: "pro-2", name: "Other synthetic product", open_session_id: "ses-9", ingredients: [] };

  beforeEach(() => {
    h.api.products.list = vi.fn(async () => [confirmed, inProgress]);
    h.api.products.classifications = vi.fn(async (id: string) =>
      id === "pro-2" ? [summary({ id: "ses-9", product_id: "pro-2", status: "determined", category: "cosmetic" })] : [],
    );
  });

  it("shows each product as a card with where its classification stands", async () => {
    renderSakti(<MyProducts />);
    const first = within(await screen.findByRole("article", { name: "Synthetic product" }));
    expect(first.getByText(en("ui.state.confirmed"))).toBeInTheDocument();
    const second = within(screen.getByRole("article", { name: "Other synthetic product" }));
    expect(second.getByText(en("ui.state.awaiting_confirmation"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.category.classical"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: new RegExp(en("product.action.review")) })).toHaveAttribute("href", "/classify/ses-9");
    expect(screen.getByRole("link", { name: new RegExp(en("product.add")) })).toHaveAttribute("href", "/my-product/new");
    expect(document.body.textContent).not.toMatch(MEDICAL);
  });

  it("searches by name or ingredient and filters by state", async () => {
    renderSakti(<MyProducts />);
    await screen.findByRole("article", { name: "Synthetic product" });
    await userEvent.type(screen.getByLabelText(en("product.search")), "ingredient a");
    expect(screen.getByText("Showing 1 of 2")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText(en("product.search")));
    await userEvent.selectOptions(screen.getByLabelText(en("product.filter")), "awaiting_confirmation");
    expect(screen.getByText("Other synthetic product")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Synthetic product" })).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText(en("product.filter")), "not_classified");
    expect(screen.getByText(en("product.noMatch"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: en("product.clearFilters") }));
    expect(screen.getByText("Showing 2 of 2")).toBeInTheDocument();
  });

  it("says so, and offers to add one, when there are none", async () => {
    h.api.products.list = vi.fn(async () => []);
    renderSakti(<MyProducts />);
    expect(await screen.findByText(en("product.emptyTitle"))).toBeInTheDocument();
    // Outside demo mode there is no sample to load.
    expect(screen.queryByRole("button", { name: en("ui.demo.loadSample") })).toBeNull();
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", async (locale) => {
    renderSakti(<MyProducts />, locale);
    await screen.findByRole("article", { name: "Synthetic product" });
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

describe("a product's page", () => {
  it("shows its state, the user's own description by section, and its history", async () => {
    h.api.products.classifications = vi.fn(async () => [summary({ status: "user_rejected", category: "cosmetic", decided_at: "2026-10-01T09:00:00Z" })]);
    renderSakti(<ProductDetail id="pro-1" />);
    expect(await screen.findByRole("heading", { level: 1, name: "Synthetic product" })).toBeInTheDocument();
    expect(screen.getByText(en("ui.state.not_classified"))).toBeInTheDocument();
    expect(screen.getByText("Synthetic purpose")).toBeInTheDocument();
    expect(screen.getByText(en("product.section.extract.title"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en("product.action.classify") })).toHaveAttribute("href", "/classify?product=pro-1");
    expect(screen.getByRole("link", { name: new RegExp(en("product.edit")) })).toHaveAttribute("href", "/my-product/pro-1/edit");
    const history = within(screen.getByRole("region", { name: en("classifier.timeline.title") }));
    expect(history.getByText(en("classifier.timeline.rejected"))).toBeInTheDocument();
  });
});

describe("the classifier's text", () => {
  it("carries no medical vocabulary and claims no legal effect", () => {
    const text = JSON.stringify([
      (saktiCatalogs.en as Record<string, unknown>).classifier,
      (saktiCatalogs.en as Record<string, unknown>).product,
    ]);
    expect(text.length).toBeGreaterThan(2000);
    expect(text).not.toMatch(MEDICAL);
    expect(text).not.toMatch(/legally classified|is approved for|you can (legally )?sell|we advise|is compliant/i);
  });
});
