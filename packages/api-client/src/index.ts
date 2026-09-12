import type {
  AIFactAction,
  AIFact,
  AIProcessing,
  AIStatus,
  CaseView,
  ConsultationRequestCreate,
  ConsultationStatus,
  ConsultationSummary,
  DoctorProfileUpdate,
  DoctorPublic,
  DoctorQueueItem,
  DocumentProcessing,
  DocumentType,
  LanguageCode,
  MedicalDocument,
  MedicalRecord,
  MedicalRecordCreate,
  MedicalRecordUpdate,
  MeResponse,
  Message,
  PatientConsultationDetail,
  PatientDashboard,
  PatientProfile,
  PatientProfileUpdate,
  Prescription,
  PrescriptionCreate,
  RecordType,
  TokenResponse,
} from "@carebridge/shared-types";

/** Error with a stable `code` the UI maps to a localised message (errors.<code>). */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const STATUS_CODES: Record<number, string> = {
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  409: "conflict",
  413: "file_too_large",
  422: "validation",
};

type Query = Record<string, string | string[] | undefined | null>;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  query?: Query;
  blob?: boolean;
}

export interface ClientConfig {
  baseUrl: string;
  getToken: () => string | null;
  onUnauthorized?: () => void;
  fetchImpl?: typeof fetch;
}

export function createApiClient(config: ClientConfig) {
  const doFetch = config.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const base = config.baseUrl.replace(/\/+$/, "") + "/api/v1";

  async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    const url = new URL(base + path);
    for (const [k, v] of Object.entries(opts.query ?? {})) {
      if (v === undefined || v === null || v === "") continue;
      for (const item of Array.isArray(v) ? v : [v]) url.searchParams.append(k, item);
    }
    const headers: Record<string, string> = {};
    const token = config.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    let body: BodyInit | undefined;
    if (opts.form) {
      body = opts.form;
    } else if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }

    let res: Response;
    try {
      res = await doFetch(url.toString(), { method: opts.method ?? "GET", headers, body });
    } catch {
      throw new ApiError(0, "network", "Network error");
    }

    if (!res.ok) {
      if (res.status === 401 && token) config.onUnauthorized?.();
      let code = STATUS_CODES[res.status] ?? "generic";
      let message = res.statusText || "Request failed";
      try {
        const data = (await res.json()) as { code?: unknown; detail?: unknown };
        if (typeof data.code === "string") code = data.code;
        if (typeof data.detail === "string") message = data.detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, code, message);
    }
    if (opts.blob) return (await res.blob()) as T;
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  const enc = encodeURIComponent;

  return {
    auth: {
      login: (email: string, password: string) =>
        request<TokenResponse>("/auth/login", { method: "POST", body: { email, password } }),
      me: () => request<MeResponse>("/auth/me"),
    },
    patient: {
      profile: () => request<PatientProfile>("/patients/me/profile"),
      updateProfile: (data: PatientProfileUpdate) =>
        request<PatientProfile>("/patients/me/profile", { method: "PUT", body: data }),
      dashboard: () => request<PatientDashboard>("/patients/me/dashboard"),
      records: (type?: RecordType) => request<MedicalRecord[]>("/patients/me/records", { query: { type } }),
      createRecord: (data: MedicalRecordCreate) =>
        request<MedicalRecord>("/patients/me/records", { method: "POST", body: data }),
      createCurrentProblem: (text: string, language: LanguageCode) =>
        request<MedicalRecord>("/patients/me/current-problems", { method: "POST", body: { text, language } }),
      updateRecord: (id: string, data: MedicalRecordUpdate) =>
        request<MedicalRecord>(`/patients/me/records/${enc(id)}`, { method: "PATCH", body: data }),
      deleteRecord: (id: string) => request<void>(`/patients/me/records/${enc(id)}`, { method: "DELETE" }),
      documents: () => request<MedicalDocument[]>("/patients/me/documents"),
      document: (id: string) => request<MedicalDocument>(`/patients/me/documents/${enc(id)}`),
      documentFile: (id: string) => request<Blob>(`/patients/me/documents/${enc(id)}/file`, { blob: true }),
      uploadDocument: (input: {
        file: File;
        documentType: DocumentType;
        sourceLanguage?: LanguageCode | null;
        title?: string | null;
      }) => {
        const form = new FormData();
        form.append("file", input.file);
        form.append("document_type", input.documentType);
        if (input.sourceLanguage) form.append("source_language", input.sourceLanguage);
        if (input.title) form.append("title", input.title);
        return request<MedicalDocument>("/patients/me/documents", { method: "POST", form });
      },
      consultations: () => request<ConsultationSummary[]>("/patients/me/consultations"),
      consultation: (id: string) => request<PatientConsultationDetail>(`/patients/me/consultations/${enc(id)}`),
      requestConsultation: (data: ConsultationRequestCreate) =>
        request<PatientConsultationDetail>("/patients/me/consultations", { method: "POST", body: data }),
      cancelConsultation: (id: string) =>
        request<PatientConsultationDetail>(`/patients/me/consultations/${enc(id)}/cancel`, { method: "POST" }),
      prescriptions: () => request<Prescription[]>("/patients/me/prescriptions"),
    },
    ai: {
      /** Explicit opt-in/out for AI processing of this patient's information. */
      setConsent: (granted: boolean) =>
        request<PatientProfile>("/patients/me/ai-consent", { method: "PUT", body: { granted } }),
      /** Run detect → normalise → extract over one record. The record is unchanged. */
      process: (recordId: string) =>
        request<AIProcessing>(`/patients/me/records/${enc(recordId)}/ai-process`, { method: "POST" }),
      /** Stored AI view for a record; no provider call. */
      forRecord: (recordId: string) => request<AIProcessing>(`/patients/me/records/${enc(recordId)}/ai`),
      /** Confirm, edit or reject one extracted item. */
      reviewFact: (factId: string, action: AIFactAction) =>
        request<AIFact>(`/patients/me/ai/facts/${enc(factId)}`, { method: "POST", body: action }),
    },
    documents: {
      /** Read a document page by page and extract reviewable items. The file itself is unchanged. */
      process: (documentId: string) =>
        request<DocumentProcessing>(`/patients/me/documents/${enc(documentId)}/process`, { method: "POST" }),
      /** Stored reading and extraction; nothing is re-run. */
      extraction: (documentId: string) =>
        request<DocumentProcessing>(`/patients/me/documents/${enc(documentId)}/extraction`),
      /** One page of the original document as a PNG, for seeing evidence in place. */
      pageImage: (documentId: string, page: number) =>
        request<Blob>(`/patients/me/documents/${enc(documentId)}/pages/${page}/image`, { blob: true }),
    },
    meta: {
      /** Public AI configuration. Contains no credentials. */
      ai: () => request<AIStatus>("/meta/ai"),
    },
    directory: {
      search: (params: { q?: string; specialization?: string; language?: LanguageCode | "" }) =>
        request<DoctorPublic[]>("/doctors", { query: params }),
      get: (id: string) => request<DoctorPublic>(`/doctors/${enc(id)}`),
    },
    doctor: {
      profile: () => request<DoctorPublic>("/doctors/me/profile"),
      updateProfile: (data: DoctorProfileUpdate) =>
        request<DoctorPublic>("/doctors/me/profile", { method: "PUT", body: data }),
      queue: (statuses?: ConsultationStatus[]) =>
        request<DoctorQueueItem[]>("/doctors/me/consultations", { query: { status: statuses } }),
      caseView: (id: string) => request<CaseView>(`/doctors/me/consultations/${enc(id)}`),
      accept: (id: string) => request<CaseView>(`/doctors/me/consultations/${enc(id)}/accept`, { method: "POST" }),
      decline: (id: string, reason?: string) =>
        request<{ id: string; status: ConsultationStatus }>(`/doctors/me/consultations/${enc(id)}/decline`, {
          method: "POST",
          body: { reason: reason || null },
        }),
      complete: (id: string) =>
        request<CaseView>(`/doctors/me/consultations/${enc(id)}/complete`, { method: "POST" }),
      setAssessment: (id: string, text: string) =>
        request<CaseView>(`/doctors/me/consultations/${enc(id)}/assessment`, {
          method: "PUT",
          body: { doctor_assessment: text },
        }),
      createPrescription: (id: string, data: PrescriptionCreate) =>
        request<Prescription>(`/doctors/me/consultations/${enc(id)}/prescriptions`, { method: "POST", body: data }),
      documentFile: (consultationId: string, documentId: string) =>
        request<Blob>(`/doctors/me/consultations/${enc(consultationId)}/documents/${enc(documentId)}/file`, {
          blob: true,
        }),
      /** A page of a document the patient shared in this consultation. */
      documentPageImage: (consultationId: string, documentId: string, page: number) =>
        request<Blob>(
          `/doctors/me/consultations/${enc(consultationId)}/documents/${enc(documentId)}/pages/${page}/image`,
          { blob: true },
        ),
    },
    messages: {
      list: (consultationId: string) => request<Message[]>(`/consultations/${enc(consultationId)}/messages`),
      send: (consultationId: string, body: string, language?: LanguageCode | null) =>
        request<Message>(`/consultations/${enc(consultationId)}/messages`, {
          method: "POST",
          body: { body, language: language ?? null },
        }),
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
