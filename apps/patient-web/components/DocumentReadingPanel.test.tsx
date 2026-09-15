import type { AIFact, DocumentPage, DocumentProcessing } from "@carebridge/shared-types";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "@/test/utils";
import { DocumentReadingPanel } from "./DocumentReadingPanel";

const fact = (over: Partial<AIFact> = {}): AIFact => ({
  id: "f2",
  category: "measurement",
  subject: "self",
  subject_evidence: null,
  value: "blood pressure 148/94",
  effective_value: "blood pressure 148/94",
  original_text: "Blood pressure: 148/94",
  evidence_quote: "Blood pressure: 148/94",
  evidence_start: 0,
  evidence_end: 22,
  confidence: 0.6,
  validation_status: "validated",
  validation_note: null,
  review_state: "pending",
  edited_value: null,
  reviewed_at: null,
  medical_record_id: null,
  source_type: "document_page",
  evidence_page_number: 2,
  evidence_bbox: [0.09, 0.1, 0.5, 0.12],
  ...over,
});

const cholesterol = fact({
  id: "f1",
  value: "total cholesterol 212 mg/dL",
  effective_value: "total cholesterol 212 mg/dL",
  original_text: "Total cholesterol: 212 mg/dL",
  evidence_quote: "Total cholesterol: 212 mg/dL",
  evidence_page_number: 1,
});

const page = (over: Partial<DocumentPage> = {}): DocumentPage => ({
  page_id: "p1",
  page_number: 1,
  method: "pdf_text_layer",
  engine: "pdfplumber 0.11",
  confidence: null,
  width: 595,
  height: 842,
  text: "LIPID PROFILE\nTotal cholesterol: 212 mg/dL",
  blocks: [],
  warnings: [],
  detected_language: "en",
  ai_status: "ok",
  ai_error_code: null,
  normalized_english: "Lipid profile. Total cholesterol 212 mg/dL.",
  unparsed: [],
  needs_review: [],
  normalization_check: { status: "ok", added_terms: [], dropped_facts: [], notes: [] },
  facts: [cholesterol],
  runs: [],
  generated_at: "2026-09-12T10:00:00Z",
  ...over,
});

const result = (over: Partial<DocumentProcessing> = {}): DocumentProcessing => ({
  document_id: "d1",
  document_status: "processed",
  status: "processed",
  error_code: null,
  extraction: {
    id: "e1",
    status: "succeeded",
    error_code: null,
    source_sha256: "ab12",
    page_count: 2,
    pages_processed: 2,
    truncated: false,
    methods: ["pdf_text_layer"],
    engines: ["pdfplumber 0.11"],
    warnings: [],
    latency_ms: 20,
    created_at: "2026-09-12T10:00:00Z",
  },
  pages: [
    page(),
    page({
      page_id: "p2",
      page_number: 2,
      text: "VITALS\nBlood pressure: 148/94 mmHg",
      normalized_english: "Vitals. Blood pressure 148/94.",
      facts: [fact()],
    }),
  ],
  usage: null,
  provider: "mock",
  model: "mock-0",
  is_external_provider: false,
  ...over,
});

const noop = {
  onGrantConsent: async () => {},
  onProcess: async () => result(),
  onReviewFact: async () => cholesterol,
  loadPage: async () => new Blob(["png"]),
};

beforeAll(() => {
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:page"), revokeObjectURL: vi.fn() });
});

describe("DocumentReadingPanel", () => {
  it("asks for consent before reading and says the original is never changed", async () => {
    const onGrantConsent = vi.fn(async () => {});
    renderWithI18n(<DocumentReadingPanel hasConsent={false} result={null} {...noop} onGrantConsent={onGrantConsent} />);

    expect(screen.getByText(/does not diagnose or prescribe/i)).toBeInTheDocument();
    expect(screen.getByText(/original file is never changed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Read document" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Allow AI processing" }));
    expect(onGrantConsent).toHaveBeenCalledOnce();
  });

  it("reads the document and keeps the page's three layers separate", async () => {
    const onProcess = vi.fn(async () => result());
    renderWithI18n(<DocumentReadingPanel hasConsent result={null} {...noop} onProcess={onProcess} />);
    expect(screen.getByText("This document has not been read yet.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Read document" }));

    expect(onProcess).toHaveBeenCalledOnce();
    expect(await screen.findByText("2 of 2 pages read")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "1 · Text read from the page" })).toHaveTextContent(
      "Total cholesterol: 212 mg/dL",
    );
    expect(screen.getByText("Copied exactly from the PDF")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "2 · English version" })).toHaveTextContent(
      "Lipid profile. Total cholesterol 212 mg/dL.",
    );
    expect(screen.getByRole("region", { name: "3 · Items found on this page" })).toHaveTextContent(
      "total cholesterol 212 mg/dL",
    );
    expect(screen.getByText("On page 1")).toBeInTheDocument();
    expect(await screen.findByAltText("Page 1 of the original document")).toBeInTheDocument();
  });

  it("labels machine transcription and its uncertainty", () => {
    renderWithI18n(
      <DocumentReadingPanel
        hasConsent
        {...noop}
        result={result({
          pages: [page({ method: "ocr", engine: "rapidocr", confidence: 0.62, warnings: ["low_ocr_confidence"] })],
        })}
      />,
    );
    expect(screen.getByText(/Read by OCR — machine transcription/)).toBeInTheDocument();
    // Confidence and engine sit behind the technical disclosure, not in the patient's reading line.
    expect(screen.getByText(/OCR confidence 62%/)).toBeInTheDocument();
    expect(screen.getByText(/hard to read/)).toBeInTheDocument();
  });

  it("moves between pages", async () => {
    renderWithI18n(<DocumentReadingPanel hasConsent result={result()} {...noop} />);
    await userEvent.click(screen.getByRole("button", { name: "Page 2" }));
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: "1 · Text read from the page" })).toHaveTextContent(
      "Blood pressure: 148/94 mmHg",
    );
    expect(screen.getByText("On page 2")).toBeInTheDocument();
  });

  it("points at the evidence on the original page", async () => {
    renderWithI18n(<DocumentReadingPanel hasConsent result={result()} {...noop} />);
    await screen.findByAltText("Page 1 of the original document");
    expect(screen.getByTestId("evidence-region")).toHaveAttribute("data-active", "false");

    await userEvent.click(screen.getByRole("button", { name: "Show on page" }));

    expect(screen.getByTestId("evidence-region")).toHaveAttribute("data-active", "true");
    expect(screen.getByRole("button", { name: "Show on page" })).toHaveAttribute("aria-pressed", "true");
  });

  it("confirms an item found in a document", async () => {
    const onReviewFact = vi.fn(async () => ({ ...cholesterol, review_state: "confirmed" as const }));
    renderWithI18n(<DocumentReadingPanel hasConsent result={result()} {...noop} onReviewFact={onReviewFact} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onReviewFact).toHaveBeenCalledWith("f1", { action: "confirm" });
    expect(await screen.findByText("Confirmed by patient")).toBeInTheDocument();
  });

  it("reports a document that could not be read without inventing content", () => {
    renderWithI18n(
      <DocumentReadingPanel
        hasConsent
        {...noop}
        result={result({ status: "failed", document_status: "failed", error_code: "document_unreadable", extraction: null, pages: [] })}
      />,
    );
    expect(screen.getByText(/could not be read. The original file is unchanged/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "3 · Items found on this page" })).not.toBeInTheDocument();
  });

  it("says when only some pages were read", () => {
    const base = result();
    renderWithI18n(
      <DocumentReadingPanel
        hasConsent
        {...noop}
        result={{ ...base, extraction: { ...base.extraction!, status: "partial", truncated: true, page_count: 12 } }}
      />,
    );
    expect(screen.getByText("Only the first 2 of 12 pages were read.")).toBeInTheDocument();
  });

  it("shows the read text when AI could not process a page", () => {
    renderWithI18n(
      <DocumentReadingPanel
        hasConsent
        {...noop}
        result={result({ pages: [page({ ai_status: "unavailable", normalized_english: null, facts: [] })] })}
      />,
    );
    expect(screen.getByText(/AI could not process this page/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "1 · Text read from the page" })).toHaveTextContent("Total cholesterol");
  });

  it("is localised", () => {
    renderWithI18n(<DocumentReadingPanel hasConsent={false} result={null} {...noop} />, "ta");
    expect(screen.getByText("இந்த ஆவணத்தைப் படி")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AI செயலாக்கத்தை இயக்கு" })).toBeInTheDocument();
  });
});
