import type { ConsultationSummary, MedicalDocument, MedicalRecord, Prescription } from "@carebridge/shared-types";
import { describe, expect, it } from "vitest";
import { buildShareItems, defaultSelection, toShareSelection } from "./sharing";

const rec = (over: Partial<MedicalRecord>): MedicalRecord => ({
  id: "r",
  type: "condition",
  title: "Hypertension",
  content: "",
  source: "patient",
  source_language: "en",
  status: "active",
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  ...over,
});

const doc = (id: string): MedicalDocument => ({
  id,
  file_name: `${id}.pdf`,
  mime_type: "application/pdf",
  size_bytes: 1000,
  document_type: "lab_report",
  title: null,
  source_language: null,
  status: "uploaded",
  uploaded_at: "2026-09-02T00:00:00Z",
});

const records = [
  rec({ id: "p-old", type: "current_problem", content: "old", created_at: "2026-01-01T00:00:00Z", status: "resolved" }),
  rec({ id: "p-new", type: "current_problem", content: "தலைவலி", source_language: "ta", created_at: "2026-09-10T00:00:00Z" }),
  rec({ id: "p-mid", type: "current_problem", content: "mid", created_at: "2026-09-05T00:00:00Z" }),
  rec({ id: "h1", type: "condition" }),
  rec({ id: "h2", type: "allergy" }),
  rec({ id: "h3", type: "condition", status: "resolved" }),
];

describe("defaultSelection", () => {
  it("pre-selects latest active problem, active history and documents; never previous opinions", () => {
    const s = defaultSelection({ records, documents: [doc("d1"), doc("d2")] });
    expect(s.current_problem).toEqual(["p-new"]);
    expect(s.medical_history.sort()).toEqual(["h1", "h2"]);
    expect(s.documents).toEqual(["d1", "d2"]);
    expect(s.previous_consultations).toEqual([]);
    expect(s.previous_prescriptions).toEqual([]);
  });

  it("handles a patient with nothing recorded", () => {
    const s = defaultSelection({ records: [], documents: [] });
    expect(Object.values(s).every((v) => v.length === 0)).toBe(true);
  });
});

describe("toShareSelection", () => {
  it("maps UI categories onto API fields", () => {
    expect(
      toShareSelection({
        current_problem: ["a"],
        medical_history: ["b"],
        documents: ["c"],
        previous_consultations: ["d"],
        previous_prescriptions: ["e"],
      }),
    ).toEqual({
      current_problem_ids: ["a"],
      medical_record_ids: ["b"],
      document_ids: ["c"],
      consultation_ids: ["d"],
      prescription_ids: ["e"],
    });
  });
});

describe("buildShareItems", () => {
  const t = (key: string, vars?: Record<string, string | number>) => (vars ? `${key}:${JSON.stringify(vars)}` : key);
  const consultations: ConsultationSummary[] = [
    { id: "c1", status: "completed", doctor: { id: "d", name: "Dr. Rajesh Iyer", specialization: "Cardiology", registration_identifier: "x" }, created_at: "2026-04-01T00:00:00Z", started_at: null, completed_at: null, prescription_count: 1 },
    { id: "c2", status: "cancelled", doctor: { id: "d", name: "Dr. X", specialization: "Y", registration_identifier: "x" }, created_at: "2026-04-01T00:00:00Z", started_at: null, completed_at: null, prescription_count: 0 },
  ];
  const prescriptions: Prescription[] = [
    { id: "rx1", consultation_id: "c1", authorship: "doctor", authored_by: consultations[0].doctor, instructions: null, created_at: "2026-04-02T00:00:00Z", items: [{ position: 1, medication: "Amlodipine 5 mg", dosage: "1", frequency: "1", duration: "1", instructions: null }] },
  ];

  it("keeps each earlier consultation/prescription attributed and skips cancelled ones", () => {
    const items = buildShareItems({ records, documents: [], consultations, prescriptions }, t, (d) => d.slice(0, 10));
    expect(items.previous_consultations.map((i) => i.id)).toEqual(["c1"]);
    expect(items.previous_consultations[0].label).toContain("Dr. Rajesh Iyer");
    expect(items.previous_prescriptions[0].label).toContain("Dr. Rajesh Iyer");
    expect(items.previous_prescriptions[0].description).toBe("Amlodipine 5 mg");
  });

  it("orders problems newest first and tags their language", () => {
    const items = buildShareItems({ records, documents: [], consultations: [], prescriptions: [] }, t, (d) => d);
    expect(items.current_problem.map((i) => i.id)).toEqual(["p-new", "p-mid", "p-old"]);
    expect(items.current_problem[0].lang).toBe("ta");
    expect(items.current_problem[0].label).toBe("தலைவலி");
  });
});
