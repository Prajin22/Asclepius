import type { CaseView } from "@carebridge/shared-types";
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderClinician } from "@/test/utils";
import { SharedClinicalInfo } from "./SharedClinicalInfo";

const base: CaseView = {
  id: "c1",
  status: "requested",
  patient: { id: "p1", display_name: "Arun Kumar", age: 46, sex: "male", preferred_language: "ta" },
  request_message: null,
  request_language: null,
  doctor_assessment: null,
  created_at: "2026-09-12T08:00:00Z",
  accepted_at: null,
  started_at: null,
  completed_at: null,
  shared_categories: [],
  current_problems: [],
  medical_history: [],
  documents: [],
  shared_consultations: [],
  shared_prescriptions: [],
  own_previous_consultations: [],
  messages: [],
  prescriptions: [],
  ai_insights: [],
  document_insights: [],
};

describe("SharedClinicalInfo", () => {
  it("says clearly when the patient did not share something", () => {
    renderClinician(<SharedClinicalInfo view={base} loadDocument={vi.fn()} />);
    expect(screen.getAllByText("The patient did not share this.")).toHaveLength(3);
  });

  it("shows the patient's own words with their language", () => {
    renderClinician(
      <SharedClinicalInfo
        view={{
          ...base,
          shared_categories: ["current_problem"],
          current_problems: [
            {
              id: "r1",
              type: "current_problem",
              title: null,
              content: "மூன்று நாட்களாக தலைவலி",
              source: "patient",
              source_language: "ta",
              status: "active",
              created_at: "2026-09-12T07:00:00Z",
              updated_at: "2026-09-12T07:00:00Z",
            },
          ],
        }}
        loadDocument={vi.fn()}
      />,
    );
    expect(screen.getByText("மூன்று நாட்களாக தலைவலி")).toHaveAttribute("lang", "ta");
    expect(screen.getByText("Written in Tamil (தமிழ்)")).toBeInTheDocument();
    expect(screen.getByText("Patient provided")).toBeInTheDocument();
  });

  it("shows a document's machine reading beside the original file", () => {
    renderClinician(
      <SharedClinicalInfo
        view={{
          ...base,
          shared_categories: ["documents"],
          documents: [
            {
              id: "d1",
              file_name: "discharge.pdf",
              mime_type: "application/pdf",
              size_bytes: 1200,
              document_type: "discharge_summary",
              title: null,
              source_language: null,
              status: "processed",
              uploaded_at: "2026-09-12T07:00:00Z",
            },
          ],
          document_insights: [
            {
              document_id: "d1",
              extraction_status: "succeeded",
              error_code: null,
              page_count: 1,
              pages_processed: 1,
              truncated: false,
              methods: ["pdf_text_layer"],
              engines: ["pdfplumber"],
              processed_at: "2026-09-12T08:00:00Z",
              pages: [],
            },
          ],
        }}
        loadDocument={vi.fn()}
      />,
    );
    expect(screen.getByText("discharge.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument(); // the original stays one click away
    expect(screen.getByText("Machine reading")).toBeInTheDocument();
    expect(screen.getByText("1 of 1 pages read")).toBeInTheDocument();
  });

  it("keeps another doctor's opinion separate and attributed", () => {
    renderClinician(
      <SharedClinicalInfo
        view={{
          ...base,
          shared_categories: ["previous_consultations"],
          shared_consultations: [
            {
              id: "c0",
              status: "completed",
              doctor: { id: "d2", name: "Dr. Rajesh Iyer", specialization: "Cardiology", registration_identifier: "R" },
              started_at: "2026-04-15T00:00:00Z",
              completed_at: "2026-04-16T00:00:00Z",
              created_at: "2026-04-15T00:00:00Z",
              doctor_assessment: "Continue amlodipine.",
            },
          ],
        }}
        loadDocument={vi.fn()}
      />,
    );
    expect(screen.getByText("Dr. Rajesh Iyer · Cardiology")).toBeInTheDocument();
    expect(screen.getByText("Continue amlodipine.")).toBeInTheDocument();
    expect(screen.getByText(/not reconciled with your assessment/)).toBeInTheDocument();
  });
});
