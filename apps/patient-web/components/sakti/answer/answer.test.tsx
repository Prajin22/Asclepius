/**
 * Ask, and the pieces a cited answer will be shown with (IP-SAKTI Phase 3.5).
 *
 * Ask is a screen only: nothing is sent, nothing is answered, and it says so.
 * The answer components are tested with synthetic, plainly non-legal fixtures
 * that exist only here: India and International stay separate panels, a
 * quotation is an evidence object with its provenance, a point without a
 * citation is never rendered, and support is described in words.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { AnswerPanel, AnswerPoint, ConfidenceBadge, EscalationSuggestion, NotCovered, SourceCitation } from ".";
import { AskPage } from "./AskPage";
import type { LaneAnswer, QuotedProvision } from "./types";

const h = vi.hoisted(() => ({ api: {} as Record<string, Record<string, ReturnType<typeof vi.fn>>> }));

vi.mock("@carebridge/api-client/react", async () => {
  const React = await import("react");
  return {
    useApi: () => h.api,
    useQuery: (fetcher: (api: unknown) => Promise<unknown>) => {
      const [data, setData] = React.useState<unknown>(undefined);
      React.useEffect(() => {
        void fetcher(h.api).then(setData);
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
      return { data, error: null, loading: data === undefined, reload: vi.fn(), setData };
    },
  };
});

const en = (key: string) => lookup(saktiCatalogs.en, key)!;
const RAW_KEY = /\b(ask|answer|ui|pages)\.[a-zA-Z]+/;

beforeEach(() => {
  h.api = { products: { list: vi.fn(async () => [{ id: "pro-1", name: "Synthetic product" }]) } };
});

describe("Ask", () => {
  it("says before anything is typed that the answer service is not enabled", () => {
    renderSakti(<AskPage />);
    expect(screen.getByText(en("ask.notEnabled.title"))).toBeInTheDocument();
    expect(screen.getAllByText(en("ask.empty.body"))).toHaveLength(2);
  });

  it("has the question, product, as-of date, jurisdiction and language controls, all labelled", async () => {
    renderSakti(<AskPage />);
    expect(screen.getByLabelText(en("ask.question"))).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Synthetic product" })).toBeInTheDocument();
    expect(screen.getByLabelText(en("ask.asOf"))).toHaveAttribute("type", "date");
    expect(screen.getByRole("group", { name: en("ask.jurisdiction") })).toBeInTheDocument();
    expect(screen.getByLabelText(en("ask.language"))).toBeInTheDocument();
  });

  it("keeps India and International as separate lanes, and at least one chosen", async () => {
    renderSakti(<AskPage />);
    const india = screen.getByRole("button", { name: en("ui.lane.india") });
    const intl = screen.getByRole("button", { name: en("ui.lane.international") });
    expect(india).toHaveAttribute("aria-pressed", "true");
    expect(intl).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: en("answer.lane.india.title") })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: en("answer.lane.international.title") })).toBeInTheDocument();

    await userEvent.click(intl);
    expect(intl).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("region", { name: en("answer.lane.international.title") })).toBeNull();
    await userEvent.click(india); // the last lane cannot be turned off
    expect(india).toHaveAttribute("aria-pressed", "true");
  });

  it("asks for a question first, then says it was not sent — and sends nothing", async () => {
    renderSakti(<AskPage />);
    await userEvent.click(screen.getByRole("button", { name: en("ask.submit") }));
    expect(screen.getByText(en("ask.validation.question"))).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(en("ask.question")), "A synthetic question");
    await userEvent.click(screen.getByRole("button", { name: en("ask.submit") }));
    expect(screen.getByText(en("ask.held.title"))).toBeInTheDocument();
    expect(Object.keys(h.api)).toEqual(["products"]);
    expect(Object.keys(h.api.products)).toEqual(["list"]);
    expect(document.querySelector("figure, blockquote")).toBeNull();
    expect(document.body.textContent).not.toMatch(/\b(section|rule|article|clause)\s+\d/i);
  });

  it.each(["hi", "ta"])("renders entirely from the %s catalogue", (locale) => {
    renderSakti(<AskPage />, locale);
    expect(document.body.textContent).not.toMatch(RAW_KEY);
  });
});

// Synthetic, plainly non-legal fixtures. They exist only in this test.
const quote = (lane: "india" | "international", n: number): QuotedProvision => ({
  text: `SYNTHETIC TEST FIXTURE ${n} - NOT A LEGAL TEXT`,
  charStart: 0,
  charEnd: 40,
  ocrDerived: n === 2,
  source: {
    provisionVersionId: `pv-${n}`, lane, authority: lane === "india" ? "india_code" : "wipo_lex",
    instrumentTitle: "Synthetic fixture instrument", locator: `Fixture label ${n}`, versionNumber: 3,
    validFrom: "2026-01-01", validTo: null, status: null, sourceTitle: "Synthetic fixture source",
    retrievedOn: "2026-09-01", approvedAt: "2026-09-02T00:00:00Z", textSha256: "c".repeat(64),
  },
});

describe("a source citation", () => {
  it("is an evidence object: the exact words, who published them, and how to check them", () => {
    renderSakti(<SourceCitation quote={quote("india", 1)} number={1} />);
    const figure = screen.getByRole("figure");
    expect(within(figure).getByText("SYNTHETIC TEST FIXTURE 1 - NOT A LEGAL TEXT").closest("blockquote")).not.toBeNull();
    expect(within(figure).getByText(en("corpus.authority.india_code"))).toBeInTheDocument();
    expect(within(figure).getByText("Synthetic fixture instrument").tagName).toBe("CITE");
    expect(within(figure).getByText("Fixture label 1")).toBeInTheDocument();
    expect(within(figure).getByText(en("ui.lane.india"))).toBeInTheDocument();
    expect(within(figure).getByText(`${"c".repeat(16)}…`)).toBeInTheDocument();
    expect(within(figure).getByText(en("answer.citation.noStatus"))).toBeInTheDocument();
  });

  it("says when part of the quotation was read by OCR", () => {
    renderSakti(<SourceCitation quote={quote("india", 2)} number={2} />);
    expect(screen.getByText(en("answer.citation.ocr"))).toBeInTheDocument();
  });
});

describe("answer points and panels", () => {
  it("never renders a point without a citation", () => {
    renderSakti(
      <ol>
        <AnswerPoint point={{ id: "p", kind: "information", statement: "An uncited statement", citations: [] }} startAt={1} />
      </ol>,
    );
    expect(screen.queryByText("An uncited statement")).toBeNull();
  });

  it("links each point to its numbered citations", () => {
    renderSakti(
      <ol>
        <AnswerPoint
          point={{ id: "p", kind: "requirement", statement: "A synthetic statement", citations: [quote("india", 1), quote("india", 2)] }}
          startAt={1}
        />
      </ol>,
    );
    expect(screen.getByText(en("answer.point.requirement"))).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: new RegExp(en("answer.point.citation")) });
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["#citation-pv-1-1", "#citation-pv-2-2"]);
    expect(screen.getAllByRole("figure")).toHaveLength(2);
  });

  it("keeps each lane in its own named panel, with its confidence in words and what is not covered", () => {
    const answer: LaneAnswer = {
      lane: "international", asOf: "2026-10-01", confidence: "partial",
      points: [{ id: "p", kind: "information", statement: "A synthetic statement", citations: [quote("international", 1)] }],
      notCovered: ["A synthetic gap"],
    };
    renderSakti(<AnswerPanel lane="international" answer={answer} />);
    const panel = screen.getByRole("region", { name: en("answer.lane.international.title") });
    expect(within(panel).getAllByText(en("ui.lane.international")).length).toBeGreaterThan(0);
    expect(within(panel).queryByText(en("ui.lane.india"))).toBeNull();
    expect(within(panel).getByText(en("answer.confidence.partial"))).toBeInTheDocument();
    expect(within(panel).getByText(en("answer.notCovered.title"))).toBeInTheDocument();
    expect(panel.textContent).not.toMatch(/\d+\s*%/);
  });

  it("shows a lane's empty state when there is no answer", () => {
    renderSakti(<AnswerPanel lane="india" empty={<p>Nothing yet</p>} />);
    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
    expect(screen.getByText(en("answer.lane.india.scope"))).toBeInTheDocument();
  });

  it("describes support in words, never a number", () => {
    for (const level of ["supported", "partial", "insufficient"] as const) {
      const { unmount } = renderSakti(<ConfidenceBadge level={level} />);
      expect(screen.getByText(en(`answer.confidence.${level}`))).toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(/\d/);
      unmount();
    }
  });

  it("renders nothing for an empty not-covered list, and offers escalation only when it exists", () => {
    renderSakti(<NotCovered items={[]} />);
    expect(document.body.textContent).toBe("");
    renderSakti(<EscalationSuggestion />);
    expect(screen.getByRole("button", { name: en("answer.escalate.action") })).toBeDisabled();
    expect(screen.getByText(en("answer.escalate.later"))).toBeInTheDocument();
  });
});
