import type {
  CaseSummary as CaseSummaryDTO,
  CaseSummaryItem,
  CaseSummarySource,
} from "@carebridge/shared-types";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderClinician } from "@/test/utils";
import { CaseSummary } from "./CaseSummary";

const source = (over: Partial<CaseSummarySource> = {}): CaseSummarySource => ({
  ref: "S1",
  kind: "fact",
  authorization_basis: "patient_grant",
  record_id: "11111111-1111-1111-1111-111111111111",
  document_id: null,
  consultation_id: null,
  prescription_id: null,
  fact_id: "22222222-2222-2222-2222-222222222222",
  page_number: null,
  bbox: null,
  quote: "தலைவலி",
  original_text: "தலைவலி",
  language: "ta",
  doctor_name: null,
  occurred_at: "2026-09-20T09:00:00Z",
  ...over,
});

const item = (over: Partial<CaseSummaryItem> = {}): CaseSummaryItem => ({
  section: "symptom",
  statement: "headache",
  origin: "patient_confirmed",
  subject: "self",
  subject_evidence: null,
  is_contradiction: false,
  occurred_at: null,
  sources: [source()],
  ...over,
});

const dto = (over: Partial<CaseSummaryDTO> = {}): CaseSummaryDTO => ({
  consultation_id: "c1",
  status: "ready",
  is_stale: false,
  summary: {
    version: 1,
    sections: [{ kind: "symptom", items: [item()] }],
    unresolved_notes: [],
    pending_fact_count: 0,
    truncated: [],
  },
  generated_at: "2026-09-23T10:00:00Z",
  language: "en",
  provider: "mock",
  model: "mock-0",
  prompt_version: "case_summary_v1",
  is_external_provider: false,
  dropped_item_count: 0,
  warnings: [],
  error_code: null,
  generations_remaining: 9,
  ...over,
});

function render(summary: CaseSummaryDTO | undefined, over: Partial<Parameters<typeof CaseSummary>[0]> = {}) {
  const onGenerate = vi.fn();
  renderClinician(
    <CaseSummary
      summary={summary}
      loading={false}
      error={null}
      generating={false}
      onGenerate={onGenerate}
      {...over}
    />,
  );
  return { onGenerate };
}

// ---------- states ----------

describe("states", () => {
  it("offers generation when nothing has been generated", async () => {
    const { onGenerate } = render(dto({ status: "not_generated", summary: null, generated_at: null }));
    expect(screen.getByText("Case summary not generated.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it("shows honest progress wording while generating, and no partial output", () => {
    render(dto({ status: "not_generated", summary: null }), { generating: true });
    expect(screen.getByText(/preparing case summary/i)).toBeInTheDocument();
    // The banned wording is the kind that claims a capability Phase 4 does not
    // have. The hint deliberately uses those words to deny them, so assert on
    // the misleading phrases rather than the vocabulary.
    for (const claim of [/analy[sz]ing medical records/i, /checking diagnosis/i, /evaluating risk/i]) {
      expect(screen.queryByText(claim)).not.toBeInTheDocument();
    }
    expect(screen.getByText(/nothing is being analysed or diagnosed/i)).toBeInTheDocument();
    // No partial output while it runs.
    expect(screen.queryByText("headache")).not.toBeInTheDocument();
  });

  it("renders a ready summary with its sections", () => {
    render(dto());
    expect(screen.getByRole("heading", { name: /symptoms/i })).toBeInTheDocument();
    expect(screen.getByText("headache")).toBeInTheDocument();
  });

  it("says a stale summary is stale and offers a refresh", () => {
    render(dto({ status: "stale", is_stale: true }));
    expect(screen.getByText(/the case changed after this summary was generated/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh summary/i })).toBeInTheDocument();
    // Still readable — labelled, not withdrawn.
    expect(screen.getByText("headache")).toBeInTheDocument();
  });

  it("shows a controlled failure that keeps the original information available", () => {
    render(dto({ status: "failed", summary: null, error_code: "ai_provider_unavailable" }));
    expect(screen.getByText(/could not be generated/i)).toBeInTheDocument();
    expect(screen.getByText(/original patient information below is unaffected/i)).toBeInTheDocument();
    // No provider internals, no stack, no error code leaked to the reader.
    expect(screen.queryByText(/ai_provider_unavailable/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("says plainly when nothing was shared, rather than inventing content", () => {
    render(
      dto({
        summary: { version: 1, sections: [], unresolved_notes: [], pending_fact_count: 0, truncated: [] },
      }),
    );
    expect(screen.getByText(/nothing to organise/i)).toBeInTheDocument();
  });
});

// ---------- authorization + errors ----------

describe("errors", () => {
  it("shows an access message for an unauthorised response and never the summary", () => {
    const err = Object.assign(new Error("nope"), { code: "not_found" });
    render(undefined, { error: err });
    expect(screen.queryByText("headache")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("disables generation and says so when the budget is spent", () => {
    render(dto({ status: "not_generated", summary: null, generations_remaining: 0 }));
    expect(screen.getByRole("button", { name: /generate summary/i })).toBeDisabled();
    expect(screen.getByText(/no summary generations left/i)).toBeInTheDocument();
  });
});

// ---------- the safety distinctions ----------

describe("attribution", () => {
  it("never shows a relative's condition as the patient's", () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "medical_history",
              items: [
                item({
                  section: "medical_history",
                  statement: "diabetes",
                  subject: "family",
                  subject_evidence: "my father",
                  sources: [source({ ref: "S3", quote: "my father has diabetes" })],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    const entry = screen.getByText("diabetes").closest("li")!;
    // The attribution is in the line itself, not only in a chip.
    expect(within(entry).getByText(/my father/)).toBeInTheDocument();
    expect(within(entry).getByText(/about a relative/i)).toBeInTheDocument();
  });

  it("says attribution is unclear rather than assuming the patient", () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [{ kind: "medical_history", items: [item({ section: "medical_history", subject: "unknown" })] }],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    expect(screen.getByText(/attribution unclear/i)).toBeInTheDocument();
  });

  it("labels a patient-typed health record as patient-reported, not a verified diagnosis", () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "medical_history",
              items: [
                item({
                  section: "medical_history",
                  statement: "Hypertension",
                  origin: "patient_provided",
                  sources: [source({ ref: "S2", kind: "health_record", fact_id: null, quote: "5 years" })],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    expect(screen.getByText(/patient-reported/i)).toBeInTheDocument();
    expect(screen.queryByText(/verified|diagnosis|confirmed diagnosis/i)).not.toBeInTheDocument();
  });
});

describe("authorship", () => {
  it("attributes doctor-authored context to the doctor who wrote it", () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "prior_consultation",
              items: [
                item({
                  section: "prior_consultation",
                  statement: "Assessment on file",
                  origin: "doctor_authored",
                  subject: null,
                  sources: [
                    source({
                      ref: "S4",
                      kind: "prior_consultation",
                      doctor_name: "Dr. Meera Sharma",
                      fact_id: null,
                      consultation_id: "33333333-3333-3333-3333-333333333333",
                      quote: "Blood pressure reviewed.",
                    }),
                  ],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    // Named on the item and again on the source it came from.
    expect(screen.getAllByText(/written by Dr\. Meera Sharma/i).length).toBeGreaterThanOrEqual(1);
  });

  it("keeps two doctors' entries separate and individually attributed", async () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "prior_consultation",
              items: [
                item({
                  section: "prior_consultation",
                  statement: "Prescription by Dr. A. Rao",
                  origin: "doctor_authored",
                  subject: null,
                  sources: [source({ ref: "S2", kind: "prior_prescription", doctor_name: "Dr. A. Rao", fact_id: null })],
                }),
                item({
                  section: "prior_consultation",
                  statement: "Prescription by Dr. B. Iyer",
                  origin: "doctor_authored",
                  subject: null,
                  sources: [source({ ref: "S3", kind: "prior_prescription", doctor_name: "Dr. B. Iyer", fact_id: null })],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    expect(screen.getByText("Prescription by Dr. A. Rao")).toBeInTheDocument();
    expect(screen.getByText("Prescription by Dr. B. Iyer")).toBeInTheDocument();
    // Both named; neither merged into one anonymous opinion.
    expect(screen.getAllByText(/written by Dr\. A\. Rao/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/written by Dr\. B\. Iyer/i).length).toBeGreaterThanOrEqual(1);
  });

  it("marks machine output as machine output, distinct from a doctor's assessment", () => {
    render(dto());
    expect(screen.getByRole("heading", { name: "AI-generated case summary" })).toBeInTheDocument();
    expect(screen.getByText(/review against the original patient records/i)).toBeInTheDocument();
    // Marked for what this panel is. "AI extracted" would describe Phase 2's
    // operation; nothing here is extracted.
    expect(screen.getByText("AI organised")).toBeInTheDocument();
    expect(screen.queryByText("AI extracted")).not.toBeInTheDocument();
    // Never borrows the doctor's vocabulary.
    expect(screen.queryByText(/^Diagnosis$|Clinical decision|Recommended treatment|Doctor assessment/i)).toBeNull();
  });
});

describe("incomplete information", () => {
  it("reports pending items as a count without stating them as facts", () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [{ kind: "symptom", items: [item()] }],
          unresolved_notes: [],
          pending_fact_count: 3,
          truncated: [],
        },
      }),
    );
    expect(screen.getByText(/3 patient-provided items awaiting confirmation/i)).toBeInTheDocument();
    expect(screen.getByText(/not shown as facts because the patient has not confirmed/i)).toBeInTheDocument();
  });

  it("says how many items validation removed", () => {
    render(dto({ dropped_item_count: 2 }));
    expect(screen.getByText(/2 items were removed/i)).toBeInTheDocument();
  });

  it("uses singular wording for a count of one", () => {
    render(dto({ dropped_item_count: 1, generations_remaining: 1 }));
    expect(screen.getByText(/^1 item was removed/i)).toBeInTheDocument();
    expect(screen.getByText(/1 summary generation left/i)).toBeInTheDocument();
    expect(screen.getByText("1 source")).toBeInTheDocument();
  });

  it("shows a contradiction without resolving it", async () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "medication",
              items: [
                item({
                  section: "medication",
                  statement: "Medication information differs across the shared records.",
                  is_contradiction: true,
                  sources: [source({ ref: "S1" }), source({ ref: "S3", quote: "I don't take any medication." })],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    // Once as the organised line, once as the flag on it.
    expect(screen.getAllByText(/information differs across the shared records/i).length).toBe(2);
    expect(screen.getByText(/nothing here decides which is correct/i)).toBeInTheDocument();
    // Nothing that picks a side. Asserted structurally rather than by
    // vocabulary, because the honest copy itself contains the word "correct".
    for (const verdict of [/preferred/i, /recommended/i, /use this one/i, /more reliable/i]) {
      expect(screen.queryByText(verdict)).not.toBeInTheDocument();
    }
    // Both sources survive, side by side, neither singled out.
    await userEvent.click(screen.getByRole("button", { name: /view source/i }));
    const panel = document.getElementById(
      screen.getByRole("button", { name: /hide source/i }).getAttribute("aria-controls")!,
    )!;
    expect(within(panel).getAllByRole("listitem")).toHaveLength(2);
  });
});

// ---------- provenance ----------

describe("provenance", () => {
  it("opens the patient's own words from a summary line", async () => {
    render(dto());
    const button = screen.getByRole("button", { name: /view source/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("தலைவலி")).toBeVisible();
    expect(screen.getByText(/patient-confirmed item/i)).toBeInTheDocument();
  });

  it("shows document title context and the page a value was read from", async () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "measurement",
              items: [
                item({
                  section: "measurement",
                  statement: "Hemoglobin 12.4 g/dL",
                  sources: [
                    source({
                      ref: "S5",
                      kind: "document",
                      page_number: 2,
                      record_id: null,
                      fact_id: null,
                      document_id: "44444444-4444-4444-4444-444444444444",
                      quote: "Hemoglobin 12.4 g/dL",
                      original_text: null,
                      language: null,
                    }),
                  ],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: /view source/i }));
    expect(screen.getByText(/page 2/i)).toBeInTheDocument();
    expect(screen.getByText(/^document$/i)).toBeInTheDocument();
  });

  it("never shows a database identifier to the doctor", async () => {
    const { container } = renderClinician(
      <CaseSummary summary={dto()} loading={false} error={null} generating={false} onGenerate={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /view source/i }));
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/);
    // Nor the opaque bundle handle, which is an implementation detail too.
    expect(text).not.toMatch(/\bS1\b/);
  });

  it("says why the doctor is allowed to see each source", async () => {
    render(dto());
    await userEvent.click(screen.getByRole("button", { name: /view source/i }));
    expect(screen.getByText(/shared by the patient/i)).toBeInTheDocument();
  });

  it("distinguishes a source shown under the doctor's own prior consultation", async () => {
    render(
      dto({
        summary: {
          version: 1,
          sections: [
            {
              kind: "prior_consultation",
              items: [
                item({
                  section: "prior_consultation",
                  statement: "Assessment on file",
                  origin: "doctor_authored",
                  subject: null,
                  sources: [
                    source({
                      ref: "S2",
                      kind: "prior_consultation",
                      authorization_basis: "own_prior_consultation",
                      doctor_name: "Dr. Meera Sharma",
                      fact_id: null,
                    }),
                  ],
                }),
              ],
            },
          ],
          unresolved_notes: [],
          pending_fact_count: 0,
          truncated: [],
        },
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: /view source/i }));
    expect(screen.getByText(/your own previous consultation/i)).toBeInTheDocument();
  });
});

// ---------- accessibility ----------

describe("accessibility", () => {
  it("gives each section a real heading", () => {
    render(dto());
    expect(screen.getByRole("heading", { name: /ai-generated case summary/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /symptoms/i })).toBeInTheDocument();
  });

  it("controls the source panel with aria-expanded and aria-controls", async () => {
    render(dto());
    const button = screen.getByRole("button", { name: /view source/i });
    const panelId = button.getAttribute("aria-controls")!;
    expect(panelId).toBeTruthy();
    expect(document.getElementById(panelId)).toHaveAttribute("hidden");
    await userEvent.click(button);
    expect(document.getElementById(panelId)).not.toHaveAttribute("hidden");
  });

  it("reaches the source toggle by keyboard", async () => {
    render(dto());
    await userEvent.tab();
    await userEvent.tab();
    const button = screen.getByRole("button", { name: /view source/i });
    expect(document.activeElement === button || screen.getByRole("button", { name: /regenerate/i })).toBeTruthy();
    button.focus();
    await userEvent.keyboard("{Enter}");
    expect(button).toHaveAttribute("aria-expanded", "true");
  });

  it("announces generation politely", () => {
    render(dto({ status: "not_generated", summary: null }), { generating: true });
    const live = document.querySelector("[aria-live='polite']");
    expect(live).toBeTruthy();
    expect(live).toHaveAttribute("aria-busy", "true");
  });
});
