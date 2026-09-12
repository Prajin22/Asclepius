import type { AIRecordInsight } from "@carebridge/shared-types";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderClinician } from "@/test/utils";
import { AIInsight } from "./AIInsight";

const ORIGINAL = "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது";

const insight = (over: Partial<AIRecordInsight> = {}): AIRecordInsight => ({
  record_id: "r1",
  status: "ok",
  original_text: ORIGINAL,
  normalization_check: { status: "ok", added_terms: [], dropped_facts: [], notes: [] },
  detected_language: "ta",
  normalized_english: "Patient reports headache. Reported duration: 2 days.",
  unparsed: [],
  provider: "mock",
  model: "mock-0",
  generated_at: "2026-09-12T10:00:00Z",
  facts: [
    {
      category: "symptom",
      subject: "self",
      subject_evidence: null,
      value: "headache",
      original_text: "தலைவலி",
      evidence_quote: "தலைவலி",
      validation_status: "validated",
      review_state: "confirmed",
    },
    {
      category: "duration",
      subject: "self",
      subject_evidence: null,
      value: "2 days",
      original_text: "இரண்டு நாட்களாக",
      evidence_quote: "இரண்டு நாட்களாக",
      validation_status: "needs_review",
      review_state: "pending",
    },
  ],
  ...over,
});

async function open() {
  await userEvent.click(screen.getByRole("button", { name: "Show AI interpretation" }));
}

describe("AIInsight", () => {
  it("is collapsed by default so the original text stays primary", () => {
    renderClinician(<AIInsight insight={insight()} />);
    expect(screen.queryByText(/Patient reports headache/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show AI interpretation" })).toBeInTheDocument();
  });

  it("shows all three layers with evidence and confirmation status", async () => {
    renderClinician(<AIInsight insight={insight()} />);
    await open();

    expect(screen.getByText("1 · Patient's words")).toBeInTheDocument();
    expect(screen.getByText(ORIGINAL)).toHaveAttribute("lang", "ta");
    expect(screen.getByText("2 · English version")).toBeInTheDocument();
    expect(screen.getByText("Patient reports headache. Reported duration: 2 days.")).toBeInTheDocument();
    expect(screen.getByText("3 · Structured items")).toBeInTheDocument();
    expect(screen.getByText("headache")).toBeInTheDocument();
    expect(screen.getByText("Confirmed by patient")).toBeInTheDocument();
    expect(screen.getByText("Not confirmed by the patient")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getAllByText("About the patient")).toHaveLength(2);
    expect(screen.getByText("Meaning preserved across all three versions")).toBeInTheDocument();
    expect(screen.getByText(/mock · mock-0/)).toBeInTheDocument();
    expect(screen.getByText(/Not clinical advice/)).toBeInTheDocument();
  });

  it("separates a relative's information from the patient's own", async () => {
    renderClinician(
      <AIInsight
        insight={insight({
          original_text: "My father has diabetes. I have a headache.",
          facts: [
            {
              category: "symptom", subject: "self", subject_evidence: null, value: "headache",
              original_text: "headache", evidence_quote: "headache", validation_status: "validated",
              review_state: "confirmed",
            },
            {
              category: "medical_history", subject: "family", subject_evidence: "My father", value: "diabetes",
              original_text: "diabetes", evidence_quote: "diabetes", validation_status: "validated",
              review_state: "pending",
            },
          ],
        })}
      />,
    );
    // Flagged even before expanding.
    expect(screen.getByText("About a relative")).toBeInTheDocument();
    await open();
    expect(screen.getByText("A relative's information — not the patient's own history.")).toBeInTheDocument();
    expect(screen.getByText("Attributed by “My father”")).toBeInTheDocument();
  });

  it("flags when the English may not match the patient's words", async () => {
    renderClinician(
      <AIInsight
        insight={insight({
          normalization_check: { status: "review", added_terms: ["diabetes"], dropped_facts: [], notes: [] },
        })}
      />,
    );
    expect(screen.getByText("The English version may not match the patient's words")).toBeInTheDocument();
    await open();
    expect(screen.getByText(/In the English but not in the patient's words: diabetes/)).toBeInTheDocument();
  });

  it("reports a degraded run rather than inventing an interpretation", async () => {
    renderClinician(<AIInsight insight={insight({ status: "unavailable", normalized_english: null, facts: [] })} />);
    await open();
    expect(screen.getByText(/AI processing was unavailable/)).toBeInTheDocument();
  });

  it("renders nothing when the record was never processed", () => {
    const { container } = renderClinician(<AIInsight insight={insight({ status: "not_processed" })} />);
    expect(container).toBeEmptyDOMElement();
  });
});
