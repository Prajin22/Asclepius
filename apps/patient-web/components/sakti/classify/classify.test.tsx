/**
 * The Classify and My Product screens (IP-SAKTI Phase 3).
 *
 * The screens decide nothing: questions, order and result come from the API.
 * What is tested is that they show it faithfully — "I don't know" is always on
 * offer and stops with what is missing; a result is shown as the classifier's,
 * awaiting the user's confirmation, with each reference's status and nothing
 * presented as a citation unless verified; the profile form has no field for a
 * conclusion; and all of it renders in English, Hindi and Tamil.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import type { ClassificationSession, ClassifierSlot, ClassifierTree, ProductProfile } from "@carebridge/shared-types";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { ClassificationFlow } from "./ClassificationFlow";
import { MyProducts } from "./MyProducts";
import { ProductForm } from "./ProductForm";
import { ReferenceList } from "./ReferenceList";

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
const RAW_KEY = /\b(classifier|product|pages|errors)\.[a-zA-Z0-9_]+\.[a-zA-Z]/;
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
    },
    products: {
      list: vi.fn(async () => []),
      create: vi.fn(async (values: unknown) => ({ id: "pro-new", revision: 1, confirmed_classification: null, open_session_id: null, ingredients: [], markers: [], ...(values as object) })),
      update: vi.fn(),
    },
  };
});

// --------------------------------------------------------------------------
// The questions
// --------------------------------------------------------------------------

describe("answering", () => {
  it("asks the current question, always offers 'I don't know', and sends only a choice id", async () => {
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByText(en("classifier.v1.purpose.question"))).toBeInTheDocument();
    expect(screen.getByLabelText(en("classifier.choice.unknown"))).toBeInTheDocument();
    expect(screen.getByText("Daily use")).toBeInTheDocument(); // the user's own description, shown back
    await userEvent.click(screen.getByLabelText(en("classifier.choice.nutrition")));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.continue") }));
    expect(h.api.classifier.respond).toHaveBeenCalledWith("ses-1", "purpose", "nutrition");
  });

  it("shows no question the tree has not reached", async () => {
    renderSakti(<ClassificationFlow id="ses-1" />);
    await screen.findByText(en("classifier.v1.purpose.question"));
    for (const later of ["classical_formula", "schedule_combination", "phytopharmaceutical"]) {
      expect(screen.queryByText(en(`classifier.v1.${later}.question`))).toBeNull();
    }
  });

  it("lets an earlier answer be changed", async () => {
    h.api.classifier.session = vi.fn(async () =>
      session({ current_node_id: "classical_formula", path: [{ node_id: "purpose", choice: "therapeutic" }] }),
    );
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.session.change") }));
    await userEvent.click(screen.getByLabelText(en("classifier.choice.external_beautification")));
    await userEvent.click(screen.getByRole("button", { name: en("classifier.session.continue") }));
    expect(h.api.classifier.respond).toHaveBeenCalledWith("ses-1", "purpose", "external_beautification");
  });
});

describe("an unknown answer", () => {
  it("stops, says what is missing and why, and shows no category", async () => {
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
    expect(await screen.findByText(en("classifier.session.stopTitle"))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.session.stopMissing").replace("{missing}", en("classifier.v1.schedule_combination.missing")))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.session.stopWhy").replace("{why}", en("classifier.v1.schedule_combination.why")))).toBeInTheDocument();
    expect(screen.getByText(en("classifier.session.stopBody"))).toBeInTheDocument();
    for (const category of TREE.categories) expect(screen.queryByText(en(`classifier.category.${category}`))).toBeNull();
    expect(screen.queryByRole("button", { name: en("classifier.session.confirm") })).toBeNull();
    expect(document.body.textContent).not.toMatch(/likely|probably|best match|estimated/i);
  });
});

// --------------------------------------------------------------------------
// The result
// --------------------------------------------------------------------------

describe("a result", () => {
  it("is the classifier's proposal, awaiting confirmation, with each reference's status", async () => {
    h.api.classifier.session = vi.fn(async () => determined("classical"));
    renderSakti(<ClassificationFlow id="ses-1" />);
    expect(await screen.findByText(en("classifier.category.classical"))).toBeInTheDocument();
    expect(screen.getAllByText(en("classifier.status.determined")).length).toBeGreaterThan(0);
    expect(screen.getByText(en("classifier.session.awaiting"))).toBeInTheDocument();
    expect(screen.getAllByText(en("classifier.reference.corpus_required"))).toHaveLength(2);
    expect(screen.getByText(en("classifier.session.resultNote"))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/legally classified|is approved|can legally sell|compliant/i);
  });

  it("is confirmed only by an explicit action naming the result shown", async () => {
    h.api.classifier.session = vi.fn(async () => determined("classical"));
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.session.confirm") }));
    expect(h.api.classifier.confirm).toHaveBeenCalledWith("ses-1", OUTCOME_ID);
    expect(await screen.findByText(/Confirmed by you on/)).toBeInTheDocument();
  });

  it("can be rejected, and then nothing is put in its place", async () => {
    h.api.classifier.session = vi.fn(async () => determined("cosmetic"));
    h.api.classifier.reject = vi.fn(async () => determined("cosmetic", { status: "user_rejected", decided_at: "2026-10-01T09:00:00Z" }));
    renderSakti(<ClassificationFlow id="ses-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("classifier.session.reject") }));
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
// My Product
// --------------------------------------------------------------------------

describe("the product profile", () => {
  it("has fields for the user's own description and none for a conclusion", () => {
    renderSakti(<ProductForm onSubmit={vi.fn()} />);
    expect(screen.getByText(en("product.factsNote"))).toBeInTheDocument();
    const labels = Array.from(document.querySelectorAll("label")).map((l) => l.textContent ?? "").join(" ");
    expect(labels).not.toMatch(/categor|classif|schedule|approved|legal/i);
  });

  it("saves what was written, without blanks", async () => {
    const onSubmit = vi.fn(async () => undefined);
    renderSakti(<ProductForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(en("product.field.name")), "Synthetic product");
    await userEvent.click(screen.getByRole("button", { name: en("product.ingredient.add") }));
    await userEvent.type(screen.getByLabelText(en("product.ingredient.name")), "Ingredient A");
    await userEvent.click(screen.getByRole("button", { name: en("product.marker.add") }));
    await userEvent.click(screen.getByRole("button", { name: en("product.create") }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      name: "Synthetic product",
      ingredients: [{ name: "Ingredient A", part_used: null, quantity: null }],
      markers: [],
      intended_use: null,
    }));
  });

  it("lists products with their own confirmed classification, or none", async () => {
    const product = {
      id: "pro-1", name: "Synthetic product", intended_use: null, dosage_form: null, administration_route: null,
      ingredients: [], preparation_method: null, classical_reference: null, extract_description: null,
      standardization_description: null, markers: [], notes: null, text_language: null, revision: 2,
      created_at: "x", updated_at: "x", open_session_id: null,
      confirmed_classification: { session_id: "s", outcome_id: "o", category: "classical", tree_version: 1, decided_at: "x" },
    } as ProductProfile;
    h.api.products.list = vi.fn(async () => [product, { ...product, id: "pro-2", name: "Other", confirmed_classification: null }]);
    renderSakti(<MyProducts />);
    expect(await screen.findByText(en("product.confirmedAs").replace("{category}", en("classifier.category.classical")))).toBeInTheDocument();
    expect(screen.getByText(en("product.notClassified"))).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(MEDICAL);
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
