/**
 * The curator's screens (IP-SAKTI Phase 2).
 *
 * Fixture text here is synthetic and non-legal, like the backend's. What is
 * tested is the contract: a provision is chosen by offsets and the text is never
 * sent; an approval names the checksum on screen and needs an explicit
 * acknowledgment when text is machine-read; the lane fixes which authorities
 * can be chosen; and every screen renders from the catalogue in all three
 * languages with no medical vocabulary.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import type {
  CorpusDiff,
  CorpusPageText,
  CorpusSourceDetail,
  CorpusSourceText,
  Provision,
  ProvisionVersionDetail,
} from "@carebridge/shared-types";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { SAKTI_NAV, SAKTI_PAGES, type SaktiPage } from "../nav";
import { CuratorUpload } from "./CuratorUpload";
import { DiffView } from "./DiffView";
import { ReviewActions } from "./ReviewActions";
import { SourceReview } from "./SourceReview";
import { SourceText } from "./SourceText";
import { documentText, linesOf, pagesOfSpan, spanBetween } from "./span";

const h = vi.hoisted(() => ({
  api: {} as Record<string, Record<string, ReturnType<typeof vi.fn>>>,
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/curator",
  useRouter: () => ({ push: h.push, replace: h.push }),
  useParams: () => ({ id: "src-1" }),
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
const MEDICAL = /patient|doctor|symptom|diagnos|prescri|medicat|medicine|allerg|clinic|hospital|health|consultation|treatment|emergency/i;
const RAW_KEY = /\b(corpus|pages|errors)\.[a-zA-Z]+\.[a-zA-Z]/;

const PAGE_ONE = ["SYNTHETIC TEST FIXTURE - NOT A LEGAL TEXT", "Alpha paragraph. The quick brown fox.", "Beta paragraph. Pack my box."].join("\n");
const PAGE_TWO = ["SYNTHETIC TEST FIXTURE - NOT A LEGAL TEXT", "Delta paragraph. Daft zebras jump."].join("\n");
const SHA = "a".repeat(64);
const TEXT_SHA = "b".repeat(64);

function pages(): CorpusPageText[] {
  return [
    { page_number: 1, char_start: 0, char_end: PAGE_ONE.length, text: PAGE_ONE, method: "pdf_text_layer", engine: "pdfplumber", confidence: null, warnings: [] },
    {
      page_number: 2, char_start: PAGE_ONE.length + 1, char_end: PAGE_ONE.length + 1 + PAGE_TWO.length, text: PAGE_TWO,
      method: "ocr", engine: "rapidocr", confidence: 0.91, warnings: [],
    },
  ];
}

function sourceText(): CorpusSourceText {
  return { source_id: "src-1", text_sha256: TEXT_SHA, text_length: PAGE_ONE.length + 1 + PAGE_TWO.length, pages: pages(), chunks: [] };
}

function source(overrides: Partial<CorpusSourceDetail> = {}): CorpusSourceDetail {
  return {
    id: "src-1", lane: "india", title: "Synthetic fixture source",
    instrument: { id: "ins-1", title: "Synthetic fixture instrument", instrument_type: "other", lane: "india" },
    source_authority: "india_code", authority_name: "India Code", document_type: "other", source_date: null,
    retrieved_on: "2026-10-01", terms_status: "unknown", ingestion_state: "parsed", ingestion_issues: [],
    review_state: "draft", page_count: 2, sha256: SHA, created_at: "2026-10-01T08:00:00Z", approved_at: null,
    source_url: null, source_reference: "Synthetic test fixture", file_name: "fixture.pdf", mime_type: "application/pdf",
    size_bytes: 1200, text_sha256: TEXT_SHA, text_length: 10, parse_error_code: null,
    extraction_methods: ["pdf_text_layer"], extraction_engines: ["pdfplumber"], parsed_at: "2026-10-01T08:01:00Z",
    uploaded_by: { id: "u1", email: "curator@ipsakti.demo" }, submitted_at: null, approved_by: null,
    issues_acknowledged: false, rejected_at: null, rejected_by: null, rejection_reason: null, versions: [],
    ...overrides,
  };
}

const provision: Provision = {
  id: "prov-1", instrument_id: "ins-1", lane: "india", locator: "Alpha", locator_type: "paragraph",
  created_at: "2026-10-01T08:00:00Z", versions: [],
};

beforeEach(() => {
  h.push.mockReset();
  h.api = {
    corpus: {
      source: vi.fn(async () => source()),
      sourceText: vi.fn(async () => sourceText()),
      instrument: vi.fn(async () => ({ provisions: [provision] })),
      instruments: vi.fn(async () => []),
      authorities: vi.fn(async () => [
        { code: "india_code", name: "India Code", lane: "india", terms_status: "unknown" },
        { code: "nba", name: "National Biodiversity Authority", lane: "india", terms_status: "unknown" },
        { code: "wipo_lex", name: "WIPO Lex", lane: "international", terms_status: "unknown" },
      ]),
      createProvision: vi.fn(async () => ({ ...provision, id: "prov-new" })),
      createVersion: vi.fn(async () => ({ version_number: 1 }) as ProvisionVersionDetail),
      createInstrument: vi.fn(async () => ({ id: "ins-new" })),
      uploadSource: vi.fn(async () => source({ id: "src-new" })),
      parse: vi.fn(async () => source()),
      submitSource: vi.fn(async () => source({ review_state: "under_review" })),
      approveSource: vi.fn(async () => source({ review_state: "approved" })),
      rejectSource: vi.fn(async () => source({ review_state: "rejected" })),
    },
  };
});

// --------------------------------------------------------------------------
// Offsets
// --------------------------------------------------------------------------

describe("span arithmetic", () => {
  it("measures every line in the document text exactly as the server does", () => {
    const all = pages();
    const document = documentText(all);
    expect(document).toBe(`${PAGE_ONE}\f${PAGE_TWO}`);
    for (const page of all) {
      for (const line of linesOf(page)) expect(document.slice(line.start, line.end)).toBe(line.text);
    }
  });

  it("spans from the first chosen line to the last, in either order, across pages", () => {
    const [one, two] = pages().map(linesOf);
    const span = spanBetween(two[1], one[1]);
    expect(span).toEqual({ start: one[1].start, end: two[1].end });
    expect(pagesOfSpan(pages(), span)).toEqual({ first: 1, last: 2 });
    expect(pagesOfSpan(pages(), spanBetween(one[2], one[2]))).toEqual({ first: 1, last: 1 });
  });
});

// --------------------------------------------------------------------------
// Taking a provision from the text
// --------------------------------------------------------------------------

describe("taking a provision from the text", () => {
  function renderText(canMark = true) {
    const onCreated = vi.fn();
    renderSakti(
      <SourceText sourceId="src-1" instrumentId="ins-1" text={sourceText()} provisions={[provision]} canMark={canMark} onCreated={onCreated} />,
    );
    return onCreated;
  }

  it("sends only the offsets of the chosen lines — never the text", async () => {
    const onCreated = renderText();
    await userEvent.click(screen.getByRole("button", { name: en("corpus.mark.lineStart").replace("{line}", "2") }));
    await userEvent.click(screen.getByRole("button", { name: en("corpus.mark.lineEnd").replace("{line}", "3") }));
    const lines = linesOf(pages()[0]);
    // The preview is the exact slice, newline included.
    expect(document.querySelector("blockquote")?.textContent).toBe(PAGE_ONE.slice(lines[1].start, lines[2].end));

    await userEvent.click(screen.getByRole("button", { name: en("corpus.mark.create") }));
    expect(h.api.corpus.createVersion).toHaveBeenCalledWith("src-1", {
      provision_id: "prov-1", char_start: lines[1].start, char_end: lines[2].end, valid_from: null, valid_to: null,
    });
    const body = h.api.corpus.createVersion.mock.calls[0][1];
    expect(Object.keys(body)).not.toContain("text");
    expect(onCreated).toHaveBeenCalled();
  });

  it("creates the provision identity first when it is new", async () => {
    renderText();
    await userEvent.click(screen.getByRole("button", { name: en("corpus.mark.lineStart").replace("{line}", "2") }));
    await userEvent.click(screen.getByRole("button", { name: en("corpus.mark.lineEnd").replace("{line}", "2") }));
    await userEvent.selectOptions(screen.getByLabelText(en("corpus.mark.provision")), en("corpus.mark.newProvision"));
    const create = screen.getByRole("button", { name: en("corpus.mark.create") });
    expect(create).toBeDisabled(); // no label yet
    await userEvent.type(screen.getByLabelText(en("corpus.mark.locator")), "Beta");
    await userEvent.click(create);
    expect(h.api.corpus.createProvision).toHaveBeenCalledWith("ins-1", { locator: "Beta", locator_type: "section" });
    expect(h.api.corpus.createVersion.mock.calls[0][1].provision_id).toBe("prov-new");
  });

  it("says when a page was machine-read, and how sure the engine was", async () => {
    renderText();
    await userEvent.click(screen.getByRole("button", { name: en("corpus.source.nextPage") }));
    expect(screen.getByText(en("corpus.method.ocr"))).toBeInTheDocument();
    expect(screen.getByText(en("corpus.method.confidence").replace("{value}", "91"))).toBeInTheDocument();
  });

  it("offers nothing to press on a source that can take no more versions", () => {
    renderText(false);
    expect(screen.queryByRole("button", { name: /Line \d/ })).toBeNull();
    expect(screen.getByText("Alpha paragraph. The quick brown fox.")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------------
// Review decisions
// --------------------------------------------------------------------------

describe("approving and rejecting", () => {
  it("shows the exact checksum being approved and needs an acknowledgment for machine-read text", async () => {
    const onApprove = vi.fn(async () => undefined);
    renderSakti(<ReviewActions checksum={SHA} needsAcknowledgment onApprove={onApprove} onReject={vi.fn()} />);
    expect(screen.getByText(SHA)).toBeInTheDocument();
    const approve = screen.getByRole("button", { name: en("corpus.review.approve") });
    expect(approve).toBeDisabled();
    await userEvent.click(screen.getByLabelText(en("corpus.review.acknowledge")));
    await userEvent.click(approve);
    expect(onApprove).toHaveBeenCalledWith(true);
  });

  it("will not reject without a reason", async () => {
    const onReject = vi.fn(async () => undefined);
    renderSakti(<ReviewActions checksum={SHA} needsAcknowledgment={false} onApprove={vi.fn()} onReject={onReject} />);
    await userEvent.click(screen.getByRole("button", { name: en("corpus.review.reject") }));
    const confirm = screen.getByRole("button", { name: en("corpus.review.confirmReject") });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText(en("corpus.review.reason")), "Not the official copy");
    await userEvent.click(confirm);
    expect(onReject).toHaveBeenCalledWith("Not the official copy");
  });

  it("explains a refusal in the curator's words", async () => {
    const onApprove = vi.fn(async () => {
      throw { code: "source_not_approved" };
    });
    renderSakti(<ReviewActions checksum={TEXT_SHA} needsAcknowledgment={false} onApprove={onApprove} onReject={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: en("corpus.review.approve") }));
    expect(await screen.findByText(en("errors.source_not_approved"))).toBeInTheDocument();
  });

  it("blocks a version whose source is not approved yet", () => {
    renderSakti(
      <ReviewActions checksum={TEXT_SHA} needsAcknowledgment={false} blocked={en("corpus.review.needsSource")} onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: en("corpus.review.approve") })).toBeDisabled();
    expect(screen.getByText(en("corpus.review.needsSource"))).toBeInTheDocument();
  });
});

describe("the source screen", () => {
  it("reads an unread draft only when asked", async () => {
    h.api.corpus.source = vi.fn(async () => source({ ingestion_state: "uploaded", text_sha256: null, page_count: null }));
    renderSakti(<SourceReview id="src-1" />);
    await userEvent.click(await screen.findByRole("button", { name: en("corpus.source.read") }));
    expect(h.api.corpus.parse).toHaveBeenCalledWith("src-1");
  });

  it("lists what needs checking and approves only with the file's checksum and an acknowledgment", async () => {
    h.api.corpus.source = vi.fn(async () =>
      source({ review_state: "under_review", ingestion_state: "needs_review", ingestion_issues: ["ocr_text_requires_verification"] }),
    );
    renderSakti(<SourceReview id="src-1" />);
    expect(await screen.findByText(en("corpus.issue.ocr_text_requires_verification"))).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(en("corpus.review.acknowledge")));
    await userEvent.click(screen.getByRole("button", { name: en("corpus.review.approve") }));
    expect(h.api.corpus.approveSource).toHaveBeenCalledWith("src-1", SHA, true);
  });

  it("shows an approved source as final, with who approved it", async () => {
    h.api.corpus.source = vi.fn(async () =>
      source({ review_state: "approved", approved_at: "2026-10-01T09:00:00Z", approved_by: { id: "u1", email: "curator@ipsakti.demo" } }),
    );
    renderSakti(<SourceReview id="src-1" />);
    expect(await screen.findByText(/curator@ipsakti\.demo/, { selector: "p.text-ink" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en("corpus.review.approve") })).toBeNull();
    expect(screen.getByText(en("corpus.source.final"))).toBeInTheDocument();
  });

  it("never shows where the file is stored", async () => {
    renderSakti(<SourceReview id="src-1" />);
    await screen.findByText(SHA);
    expect(document.body.textContent).not.toMatch(/storage|local:|corpus\/sources\//);
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", async (locale) => {
    h.api.corpus.source = vi.fn(async () =>
      source({ review_state: "under_review", ingestion_state: "needs_review", ingestion_issues: ["page_without_text"] }),
    );
    renderSakti(<SourceReview id="src-1" />, locale);
    await screen.findByText(lookup(saktiCatalogs[locale], "corpus.issue.page_without_text")!);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBeGreaterThan(0));
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

// --------------------------------------------------------------------------
// Upload
// --------------------------------------------------------------------------

describe("uploading a source", () => {
  const pdf = () => new File(["%PDF-1.4"], "fixture.pdf", { type: "application/pdf" });

  async function chooseFile() {
    renderSakti(<CuratorUpload />);
    const file = pdf();
    await userEvent.upload(screen.getByLabelText(en("corpus.upload.file")), file);
    await userEvent.click(screen.getByRole("button", { name: en("corpus.wizard.next") }));
    await screen.findByRole("option", { name: en("corpus.authority.india_code") });
    return file;
  }

  async function fillAndUpload() {
    const file = await chooseFile();
    await userEvent.type(screen.getByLabelText(en("corpus.upload.instrumentTitleLabel")), "Synthetic fixture instrument");
    await userEvent.type(screen.getByLabelText(en("corpus.upload.issuedBy")), "The test suite");
    await userEvent.type(screen.getByLabelText(en("corpus.upload.documentTitle")), "Synthetic fixture source");
    await userEvent.type(screen.getByLabelText(en("corpus.upload.sourceReference")), "Synthetic test fixture");
    await userEvent.click(screen.getByRole("button", { name: en("corpus.upload.submit") }));
    return file;
  }

  beforeEach(() => {
    h.api.corpus.uploadSource = vi.fn(async () => source({ id: "src-new", ingestion_state: "uploaded", page_count: null }));
    h.api.corpus.parse = vi.fn(async () => source({ id: "src-new" }));
    h.api.corpus.submitSource = vi.fn(async () => source({ id: "src-new", review_state: "under_review" }));
  });

  it("is five named steps, and the first needs a file before it continues", async () => {
    renderSakti(<CuratorUpload />);
    const steps = screen.getByRole("list", { name: en("corpus.wizard.progress") });
    expect(within(steps).getAllByRole("listitem").map((li) => li.textContent)).toEqual(
      ["select", "metadata", "parse", "review", "submit"].map((k, i) => `${i + 1}${en(`corpus.wizard.steps.${k}`)}`),
    );
    expect(within(steps).getAllByRole("listitem")[0]).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("button", { name: en("corpus.wizard.next") })).toBeDisabled();
  });

  it("offers only the authorities of the chosen lane", async () => {
    renderSakti(<CuratorUpload />);
    await userEvent.click(screen.getByRole("radio", { name: new RegExp(en("ui.lane.international")) }));
    await userEvent.upload(screen.getByLabelText(en("corpus.upload.file")), pdf());
    await userEvent.click(screen.getByRole("button", { name: en("corpus.wizard.next") }));
    const authority = await screen.findByLabelText(en("corpus.authority.label"));
    await screen.findByRole("option", { name: en("corpus.authority.wipo_lex") });
    expect(within(authority).getAllByRole("option").map((o) => o.textContent)).toEqual([en("corpus.authority.wipo_lex")]);
  });

  it("creates the instrument and stores the file with its provenance, reading nothing yet", async () => {
    const file = await fillAndUpload();
    expect(h.api.corpus.createInstrument).toHaveBeenCalledWith({
      lane: "india", instrument_type: "act", title: "Synthetic fixture instrument", issued_by: "The test suite", description: null,
    });
    expect(h.api.corpus.uploadSource).toHaveBeenCalledWith(
      expect.objectContaining({
        file, lane: "india", instrumentId: "ins-new", sourceAuthority: "india_code", sourceReference: "Synthetic test fixture",
        sourceUrl: null,
      }),
    );
    expect(await screen.findByText(en("corpus.wizard.stored"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: en("corpus.wizard.steps.parse") })).toBeInTheDocument();
    expect(h.api.corpus.parse).not.toHaveBeenCalled();
  });

  it("reads, reviews and submits — and approves nothing", async () => {
    await fillAndUpload();
    await userEvent.click(await screen.findByRole("button", { name: en("corpus.source.read") }));
    expect(h.api.corpus.parse).toHaveBeenCalledWith("src-new");
    await userEvent.click(await screen.findByRole("button", { name: en("corpus.wizard.next") }));

    expect(screen.getByRole("heading", { name: en("corpus.wizard.steps.review") })).toBeInTheDocument();
    expect(screen.getByText("fixture.pdf")).toBeInTheDocument();
    expect(screen.getByText(SHA)).toBeInTheDocument();
    expect(screen.getByText(en("corpus.wizard.jurisdiction"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en("corpus.wizard.openText") })).toHaveAttribute("href", "/curator/sources/src-new");
    await userEvent.click(screen.getByRole("button", { name: en("corpus.wizard.next") }));

    await userEvent.click(screen.getByRole("button", { name: en("corpus.source.submit") }));
    expect(h.api.corpus.submitSource).toHaveBeenCalledWith("src-new");
    expect(await screen.findByText(en("corpus.wizard.submitted"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: en("corpus.wizard.toApprove") })).toHaveAttribute("href", "/curator/approve");
    expect(h.api.corpus.approveSource).not.toHaveBeenCalled();
  });

  it("explains a refused upload", async () => {
    h.api.corpus.uploadSource = vi.fn(async () => {
      throw { code: "duplicate_source" };
    });
    await fillAndUpload();
    expect(await screen.findByText(en("errors.duplicate_source"))).toBeInTheDocument();
  });

  it("will not upload without saying where the file came from", async () => {
    await chooseFile();
    await userEvent.type(screen.getByLabelText(en("corpus.upload.instrumentTitleLabel")), "x");
    await userEvent.type(screen.getByLabelText(en("corpus.upload.issuedBy")), "x");
    await userEvent.type(screen.getByLabelText(en("corpus.upload.documentTitle")), "x");
    expect(screen.getByRole("button", { name: en("corpus.upload.submit") })).toBeDisabled();
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", async (locale) => {
    renderSakti(<CuratorUpload />, locale);
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

// --------------------------------------------------------------------------
// Diff
// --------------------------------------------------------------------------

describe("the diff", () => {
  const diff: CorpusDiff = {
    baseline: { kind: "version", id: "v1", label: "v1", approved_at: "2026-09-01T00:00:00Z" },
    stats: { added: 1, removed: 0, changed: 1, unchanged: 7 },
    blocks: [
      { op: "equal", old_start: 1, new_start: 1, lines: [], skipped: 4, tail: ["Gamma paragraph."] },
      {
        op: "replace", old_start: 6, new_start: 6, old: ["Pack my box."], new: ["Pack my crate."],
        words: [{ op: "equal", text: "Pack my " }, { op: "delete", text: "box" }, { op: "insert", text: "crate" }, { op: "equal", text: "." }],
      },
      { op: "insert", old_start: 7, new_start: 7, new: ["Zeta paragraph."] },
    ],
  };

  it("marks removed and added text by more than colour, and says what it folded away", () => {
    renderSakti(<DiffView diff={diff} noBaseline="none" />);
    expect(screen.getByText("box").closest("del")).not.toBeNull();
    expect(screen.getByText("crate").closest("ins")).not.toBeNull();
    expect(screen.getByText(en("corpus.diff.unchanged").replace("{count}", "4"))).toBeInTheDocument();
    expect(screen.getByText("Zeta paragraph.")).toBeInTheDocument();
    expect(screen.getAllByText(`${en("corpus.diff.added")}:`, { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText(/1 added · 0 removed · 1 changed · 7 unchanged/)).toBeInTheDocument();
  });

  it("says plainly when there is nothing to compare against", () => {
    renderSakti(<DiffView diff={{ ...diff, baseline: null }} noBaseline={en("corpus.version.noBaseline")} />);
    expect(screen.getByText(en("corpus.version.noBaseline"))).toBeInTheDocument();
  });

  it("sets the two texts side by side on a wide screen, and can fold them back inline", async () => {
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    try {
      renderSakti(<DiffView diff={diff} noBaseline="none" />);
      const table = screen.getByRole("table");
      expect(within(table).getByRole("columnheader", { name: en("corpus.diff.before") })).toBeInTheDocument();
      expect(within(table).getByRole("columnheader", { name: en("corpus.diff.after") })).toBeInTheDocument();
      expect(screen.getByText("box").closest("del")).not.toBeNull();
      expect(screen.getByText("crate").closest("ins")).not.toBeNull();
      const inline = screen.getByRole("button", { name: en("corpus.diff.inline") });
      await userEvent.click(inline);
      expect(inline).toHaveAttribute("aria-pressed", "true");
      expect(screen.queryByRole("table")).toBeNull();
    } finally {
      window.matchMedia = original;
    }
  });

  it("is always one column on a narrow screen", () => {
    renderSakti(<DiffView diff={diff} noBaseline="none" />);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("button", { name: en("corpus.diff.split") })).toBeNull();
  });
});

// --------------------------------------------------------------------------
// Navigation and vocabulary
// --------------------------------------------------------------------------

describe("the curator's area", () => {
  it("has its four screens built, and only the user's dashboard, Classify and My Products besides", () => {
    // Phase 3 built Classify and My Products, Phase 3.5 the dashboard; everything else is still a placeholder.
    const built = new Set<SaktiPage>([...SAKTI_NAV.curator.map((item) => item.page), "classify", "myProduct", "dashboard"]);
    for (const [page, info] of Object.entries(SAKTI_PAGES) as [SaktiPage, (typeof SAKTI_PAGES)[SaktiPage]][]) {
      expect(info.available, page).toBe(built.has(page));
    }
  });

  it("carries no medical vocabulary and claims no legal authority", () => {
    // Hindi and Tamil are checked for medical vocabulary by the catalogue's own tests.
    const corpus = JSON.stringify((saktiCatalogs.en as Record<string, unknown>).corpus);
    expect(corpus.length).toBeGreaterThan(1000);
    expect(corpus).not.toMatch(MEDICAL);
    expect(corpus).not.toMatch(/legal advice is|we advise|is the law|legally binding/i);
  });
});
