import type { TFunction } from "@carebridge/i18n";
import type {
  ConsultationSummary,
  MedicalDocument,
  MedicalRecord,
  Prescription,
  ShareCategory,
  ShareSelection,
} from "@carebridge/shared-types";

export type SelectionState = Record<ShareCategory, string[]>;

export interface ShareItem {
  id: string;
  label: string;
  description?: string;
  lang?: string | null;
}

export interface ShareSource {
  records: MedicalRecord[];
  documents: MedicalDocument[];
  consultations: ConsultationSummary[];
  prescriptions: Prescription[];
}

export function emptySelection(): SelectionState {
  return {
    current_problem: [],
    medical_history: [],
    documents: [],
    previous_consultations: [],
    previous_prescriptions: [],
  };
}

const newestFirst = <T extends { created_at: string }>(a: T, b: T) => b.created_at.localeCompare(a.created_at);

/**
 * Initial choices shown to the patient (they can change every one):
 * ☑ latest current problem, ☑ active medical history, ☑ documents,
 * ☐ previous consultations, ☐ previous prescriptions.
 */
export function defaultSelection(src: Pick<ShareSource, "records" | "documents">): SelectionState {
  const latestProblem = src.records
    .filter((r) => r.type === "current_problem" && r.status === "active")
    .sort(newestFirst)[0];
  return {
    ...emptySelection(),
    current_problem: latestProblem ? [latestProblem.id] : [],
    medical_history: src.records.filter((r) => r.type !== "current_problem" && r.status === "active").map((r) => r.id),
    documents: src.documents.map((d) => d.id),
  };
}

export function toShareSelection(s: SelectionState): ShareSelection {
  return {
    current_problem_ids: s.current_problem,
    medical_record_ids: s.medical_history,
    document_ids: s.documents,
    consultation_ids: s.previous_consultations,
    prescription_ids: s.previous_prescriptions,
  };
}

function excerpt(text: string, max = 140): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean;
}

export function buildShareItems(
  src: ShareSource,
  t: TFunction,
  formatDate: (iso: string) => string,
): Record<ShareCategory, ShareItem[]> {
  const problems = src.records.filter((r) => r.type === "current_problem").sort(newestFirst);
  const history = src.records.filter((r) => r.type !== "current_problem").sort(newestFirst);
  return {
    current_problem: problems.map((r) => ({
      id: r.id,
      label: excerpt(r.content),
      description: `${formatDate(r.created_at)} · ${t(`recordStatus.${r.status}`)}`,
      lang: r.source_language,
    })),
    medical_history: history.map((r) => ({
      id: r.id,
      label: r.title ?? t(`recordType.${r.type}`),
      description: [t(`recordType.${r.type}`), t(`recordStatus.${r.status}`), t(`source.${r.source}`)].join(" · "),
    })),
    documents: [...src.documents]
      .sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at))
      .map((d) => ({
        id: d.id,
        label: d.title || d.file_name,
        description: `${t(`documentType.${d.document_type}`)} · ${formatDate(d.uploaded_at)}`,
      })),
    previous_consultations: src.consultations
      .filter((c) => c.status !== "cancelled")
      .map((c) => ({
        id: c.id,
        label: t("request.consultationItem", { doctor: c.doctor.name, date: formatDate(c.created_at) }),
        description: `${c.doctor.specialization} · ${t(`status.${c.status}`)}`,
      })),
    previous_prescriptions: src.prescriptions.map((p) => ({
      id: p.id,
      label: t("request.prescriptionItem", {
        doctor: p.authored_by.name,
        date: formatDate(p.created_at),
        count: p.items.length,
      }),
      description: p.items.map((i) => i.medication).join(", "),
    })),
  };
}
