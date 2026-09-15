import type { AIFact, AIProcessing } from "@carebridge/shared-types";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "@/test/utils";
import { AIAssistPanel } from "./AIAssistPanel";

const ORIGINAL = "எனக்கு இரண்டு நாட்களாக தலைவலி உள்ளது";

const fact = (over: Partial<AIFact> = {}): AIFact => ({
  id: "f1",
  category: "symptom",
  subject: "self",
  subject_evidence: null,
  value: "headache",
  effective_value: "headache",
  original_text: "தலைவலி",
  evidence_quote: "தலைவலி",
  evidence_start: 24,
  evidence_end: 30,
  confidence: 0.75,
  validation_status: "validated",
  validation_note: null,
  review_state: "pending",
  edited_value: null,
  reviewed_at: null,
  medical_record_id: null,
  ...over,
});

const result = (over: Partial<AIProcessing> = {}): AIProcessing => ({
  record_id: "r1",
  status: "ok",
  error_code: null,
  original_text: ORIGINAL,
  normalization_check: { status: "ok", added_terms: [], dropped_facts: [], notes: [] },
  usage: null,
  detected_language: "ta",
  language_confidence: 0.9,
  normalized_english: "Patient reports headache. Reported duration: 2 days.",
  unparsed: [],
  needs_review: [],
  facts: [fact()],
  runs: [
    {
      artifact_id: "a1",
      operation: "extraction",
      provider: "mock",
      model: "mock-0",
      prompt_version: "medical_extraction_v2",
      status: "succeeded",
      latency_ms: 3,
      input_tokens: null,
      output_tokens: null,
      estimated_cost_usd: 0,
      cached: false,
      created_at: "2026-09-12T10:00:00Z",
    },
  ],
  generated_at: "2026-09-12T10:00:00Z",
  provider: "mock",
  model: "mock-0",
  is_external_provider: false,
  ...over,
});

const noop = {
  onGrantConsent: async () => {},
  onProcess: async () => result(),
  onReviewFact: async () => fact(),
};

describe("AIAssistPanel", () => {
  it("always states that the AI does not diagnose", () => {
    renderWithI18n(<AIAssistPanel originalText={ORIGINAL} hasConsent={false} result={null} {...noop} />);
    expect(screen.getByText(/does not diagnose or prescribe/i)).toBeInTheDocument();
  });

  it("asks for consent first and does not offer processing", async () => {
    const onGrantConsent = vi.fn(async () => {});
    renderWithI18n(
      <AIAssistPanel originalText={ORIGINAL} hasConsent={false} result={null} {...noop} onGrantConsent={onGrantConsent} />,
    );
    expect(screen.queryByRole("button", { name: "Process with AI" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Allow AI processing" }));
    expect(onGrantConsent).toHaveBeenCalledOnce();
  });

  it("shows all three layers separately after processing", async () => {
    const onProcess = vi.fn(async () => result());
    renderWithI18n(<AIAssistPanel originalText={ORIGINAL} hasConsent result={null} {...noop} onProcess={onProcess} />);

    await userEvent.click(screen.getByRole("button", { name: "Process with AI" }));

    expect(onProcess).toHaveBeenCalledOnce();
    expect(await screen.findByRole("region", { name: "1 · Your words" })).toHaveTextContent(ORIGINAL);
    expect(screen.getByRole("region", { name: "2 · English version" })).toHaveTextContent(
      "Patient reports headache. Reported duration: 2 days.",
    );
    expect(screen.getByRole("region", { name: "3 · Structured items" })).toHaveTextContent("headache");
    expect(screen.getByText("Machine-generated")).toBeInTheDocument();
    expect(screen.getByText(/Detected language/)).toHaveTextContent("தமிழ்");
    expect(screen.getByText("The English version matches your words")).toBeInTheDocument();
    expect(screen.getByText("Awaiting patient confirmation")).toBeInTheDocument();
    expect(screen.getByText("About you")).toBeInTheDocument();
  });

  it("warns when the English version changed the meaning", () => {
    renderWithI18n(
      <AIAssistPanel
        originalText={ORIGINAL}
        hasConsent
        result={result({
          normalization_check: {
            status: "review",
            added_terms: ["diabetes"],
            dropped_facts: ["cough"],
            notes: ["attribution_lost"],
          },
        })}
        {...noop}
      />,
    );
    expect(screen.getByText("The English wording needs a check")).toBeInTheDocument();
    expect(screen.getByText(/In the English but not in your words: diabetes/)).toBeInTheDocument();
    expect(screen.getByText(/missing from the English: cough/)).toBeInTheDocument();
    expect(screen.getByText(/does not say this was about a family member/)).toBeInTheDocument();
  });

  it("marks a relative's condition as not the patient's own", () => {
    renderWithI18n(
      <AIAssistPanel
        originalText="My father has diabetes."
        hasConsent
        result={result({
          facts: [
            fact({ id: "f2", category: "medical_history", subject: "family", subject_evidence: "My father",
                   value: "diabetes", effective_value: "diabetes", evidence_quote: "diabetes" }),
          ],
        })}
        {...noop}
      />,
    );
    expect(screen.getByText("About a family member")).toBeInTheDocument();
    expect(screen.getByText("Attributed by: “My father”")).toBeInTheDocument();
    expect(screen.getByText(/Recorded as family history — not as your own condition/)).toBeInTheDocument();
  });

  it("lists the patient's own items before a relative's", () => {
    renderWithI18n(
      <AIAssistPanel
        originalText="My father has diabetes. I have a headache."
        hasConsent
        result={result({
          facts: [
            fact({ id: "fam", subject: "family", subject_evidence: "My father", value: "diabetes",
                   effective_value: "diabetes", evidence_quote: "diabetes", category: "medical_history" }),
            fact({ id: "own" }),
          ],
        })}
        {...noop}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("headache");
    expect(items[1]).toHaveTextContent("diabetes");
  });

  it("confirms a fact and reflects the new state", async () => {
    const onReviewFact = vi.fn(async () => fact({ review_state: "confirmed" }));
    renderWithI18n(
      <AIAssistPanel originalText={ORIGINAL} hasConsent result={result()} {...noop} onReviewFact={onReviewFact} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onReviewFact).toHaveBeenCalledWith("f1", { action: "confirm" });
    expect(await screen.findByText("Confirmed by patient")).toBeInTheDocument();
  });

  it("lets the patient correct a value", async () => {
    const onReviewFact = vi.fn(async () =>
      fact({ review_state: "edited", edited_value: "severe headache", effective_value: "severe headache" }),
    );
    renderWithI18n(
      <AIAssistPanel originalText={ORIGINAL} hasConsent result={result()} {...noop} onReviewFact={onReviewFact} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const input = screen.getByLabelText("Corrected value");
    await userEvent.clear(input);
    await userEvent.type(input, "severe headache");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onReviewFact).toHaveBeenCalledWith("f1", { action: "edit", value: "severe headache" });
    expect(await screen.findByText("severe headache")).toBeInTheDocument();
  });

  it("rejects a fact", async () => {
    const onReviewFact = vi.fn(async () => fact({ review_state: "rejected" }));
    renderWithI18n(
      <AIAssistPanel originalText={ORIGINAL} hasConsent result={result()} {...noop} onReviewFact={onReviewFact} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onReviewFact).toHaveBeenCalledWith("f1", { action: "reject" });
  });

  it("shows a degraded state without inventing content", () => {
    renderWithI18n(
      <AIAssistPanel
        originalText={ORIGINAL}
        hasConsent
        result={result({ status: "unavailable", error_code: "ai_timeout", normalized_english: null, facts: [] })}
        {...noop}
      />,
    );
    expect(screen.getByText("AI is unavailable right now")).toBeInTheDocument();
    expect(screen.queryByText("headache")).not.toBeInTheDocument();
  });

  it("explains a rate limit in plain language", async () => {
    const onProcess = vi.fn(async () => {
      throw { code: "ai_rate_limited" };
    });
    renderWithI18n(<AIAssistPanel originalText={ORIGINAL} hasConsent result={null} {...noop} onProcess={onProcess} />);
    await userEvent.click(screen.getByRole("button", { name: "Process with AI" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reached the AI processing limit/);
  });

  it("says plainly when nothing could be supported by the patient's words", () => {
    renderWithI18n(<AIAssistPanel originalText={ORIGINAL} hasConsent result={result({ facts: [] })} {...noop} />);
    expect(screen.getByText(/did not find anything/i)).toBeInTheDocument();
  });

  it("is localised", () => {
    renderWithI18n(<AIAssistPanel originalText={ORIGINAL} hasConsent={false} result={null} {...noop} />, "ta");
    expect(screen.getByRole("button", { name: "AI செயலாக்கத்தை இயக்கு" })).toBeInTheDocument();
  });
});
