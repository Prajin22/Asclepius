import type { DocumentInsight as DocumentInsightData } from "@carebridge/shared-types";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { renderClinician } from "@/test/utils";
import { DocumentInsight } from "./DocumentInsight";

const TEXT = "Diagnosis: Hypertension\nFamily history: Father has diabetes.";

const insight = (over: Partial<DocumentInsightData> = {}): DocumentInsightData => ({
  document_id: "d1",
  extraction_status: "succeeded",
  error_code: null,
  page_count: 1,
  pages_processed: 1,
  truncated: false,
  methods: ["ocr"],
  engines: ["rapidocr-onnxruntime 1.4.4"],
  processed_at: "2026-09-12T10:00:00Z",
  pages: [
    {
      page_number: 1,
      method: "ocr",
      engine: "rapidocr-onnxruntime 1.4.4",
      confidence: 0.91,
      text: TEXT,
      blocks: [],
      warnings: [],
      detected_language: "en",
      ai_status: "ok",
      normalized_english: "Diagnosis: hypertension. Family history: father has diabetes.",
      normalization_check: { status: "ok", added_terms: [], dropped_facts: [], notes: [] },
      facts: [
        {
          category: "medical_history",
          subject: "self",
          subject_evidence: null,
          value: "hypertension",
          original_text: "Hypertension",
          evidence_quote: "Hypertension",
          validation_status: "validated",
          review_state: "confirmed",
          evidence_page_number: 1,
          evidence_bbox: [0.1, 0.1, 0.4, 0.12],
        },
        {
          category: "medical_history",
          subject: "family",
          subject_evidence: "Father",
          value: "diabetes",
          original_text: "diabetes",
          evidence_quote: "diabetes",
          validation_status: "validated",
          review_state: "pending",
          evidence_page_number: 1,
          evidence_bbox: [0.1, 0.2, 0.5, 0.22],
        },
      ],
    },
  ],
  ...over,
});

const open = () => userEvent.click(screen.getByRole("button", { name: "Show machine reading" }));

beforeAll(() => {
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:page"), revokeObjectURL: vi.fn() });
});

describe("DocumentInsight", () => {
  it("is collapsed by default so the original file stays primary", () => {
    renderClinician(<DocumentInsight insight={insight()} />);
    expect(screen.getByText("1 of 1 pages read")).toBeInTheDocument();
    expect(screen.getByText("About a relative")).toBeInTheDocument(); // flagged before opening
    expect(screen.queryByText(/Father has diabetes/)).not.toBeInTheDocument();
  });

  it("shows how the page was read, what was read, and the extracted items", async () => {
    renderClinician(<DocumentInsight insight={insight()} />);
    await open();

    expect(screen.getByText(/Not clinical advice/)).toBeInTheDocument();
    expect(screen.getByText(/Read by OCR — machine transcription, can misread/)).toBeInTheDocument();
    expect(screen.getByText(/OCR confidence 91%/)).toBeInTheDocument();
    expect(screen.getByText(/Family history: Father has diabetes\./)).toHaveAttribute("lang", "en");
    expect(screen.getByText("Diagnosis: hypertension. Family history: father has diabetes.")).toBeInTheDocument();
    expect(screen.getByText("Confirmed by patient")).toBeInTheDocument();
    expect(screen.getByText("Not confirmed by the patient")).toBeInTheDocument();
    expect(screen.getByText("A relative's information — not the patient's own history.")).toBeInTheDocument();
    expect(screen.getAllByText("Page 1")).toHaveLength(2);
  });

  it("outlines an item's evidence on the original page", async () => {
    renderClinician(<DocumentInsight insight={insight()} loadPage={async () => new Blob(["png"])} />);
    await open();
    await screen.findByAltText("Page 1 of the original document");

    await userEvent.click(screen.getAllByRole("button", { name: "Show on page" })[1]);

    const regions = screen.getAllByTestId("evidence-region");
    expect(regions.map((r) => r.getAttribute("data-active"))).toEqual(["false", "true"]);
  });

  it("does not offer a reading for a document that could not be read", () => {
    renderClinician(<DocumentInsight insight={insight({ extraction_status: "failed", pages: [], pages_processed: 0 })} />);
    expect(screen.getByText("This document could not be read. Use the original file.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show machine reading" })).not.toBeInTheDocument();
  });
});
