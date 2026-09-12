import { describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "../src/index";

type FetchCall = [string, RequestInit];

function fakeFetch(status: number, body: unknown, contentType = "application/json") {
  return vi.fn(async (..._args: Parameters<typeof fetch>) =>
    new Response(body === undefined ? null : typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": contentType },
    }),
  );
}

describe("api client", () => {
  it("sends bearer token and builds repeated query params", async () => {
    const fetchImpl = fakeFetch(200, []);
    const api = createApiClient({ baseUrl: "http://api.test/", getToken: () => "tok", fetchImpl });
    await api.doctor.queue(["requested", "active"]);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/doctors/me/consultations?status=requested&status=active");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("omits empty query values and sends JSON bodies", async () => {
    const fetchImpl = fakeFetch(200, []);
    const api = createApiClient({ baseUrl: "http://api.test", getToken: () => null, fetchImpl });
    await api.directory.search({ q: "", language: "ta" });
    expect(fetchImpl.mock.calls[0][0]).toBe("http://api.test/api/v1/doctors?language=ta");

    await api.patient.createCurrentProblem("தலைவலி", "ta");
    const init = fetchImpl.mock.calls[1][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ text: "தலைவலி", language: "ta" });
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("uses server error codes when present", async () => {
    const api = createApiClient({
      baseUrl: "http://api.test",
      getToken: () => "t",
      fetchImpl: fakeFetch(422, { detail: "File content does not match", code: "content_mismatch" }),
    });
    await expect(api.patient.documents()).rejects.toMatchObject({ status: 422, code: "content_mismatch" });
  });

  it("maps FastAPI validation errors (no code) to 'validation'", async () => {
    const api = createApiClient({
      baseUrl: "http://api.test",
      getToken: () => "t",
      fetchImpl: fakeFetch(422, { detail: [{ loc: ["body", "x"], msg: "bad" }] }),
    });
    const err = await api.patient.profile().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("validation");
  });

  it("calls onUnauthorized on 401 when a token was sent", async () => {
    const onUnauthorized = vi.fn();
    const api = createApiClient({
      baseUrl: "http://api.test",
      getToken: () => "expired",
      onUnauthorized,
      fetchImpl: fakeFetch(401, { detail: "Invalid or expired token" }),
    });
    await expect(api.auth.me()).rejects.toMatchObject({ code: "unauthorized" });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("reports network failures with code 'network'", async () => {
    const api = createApiClient({
      baseUrl: "http://api.test",
      getToken: () => null,
      fetchImpl: vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    });
    await expect(api.auth.login("a@b.c", "x")).rejects.toMatchObject({ status: 0, code: "network" });
  });

  it("signs doctors up and sends reviews to the admin endpoints", async () => {
    const fetchImpl = fakeFetch(200, {});
    const api = createApiClient({ baseUrl: "http://api.test", getToken: () => "t", fetchImpl });
    await api.auth.applyAsDoctor({
      email: "d@example.com",
      password: "password1",
      name: "Dr. D",
      specialization: "Pediatrics",
      qualification: "MBBS",
      registration_identifier: "R-1",
      clinic_name: null,
      clinic_address: null,
      phone: null,
      languages: ["en"],
    });
    await api.admin.doctors("pending");
    await api.admin.rejectDoctor("d 1", "Not on the register");
    const calls = fetchImpl.mock.calls as unknown as FetchCall[];
    expect(calls.map(([url, init]) => `${init.method} ${url}`)).toEqual([
      "POST http://api.test/api/v1/auth/register-doctor",
      "GET http://api.test/api/v1/admin/doctors?status=pending",
      "POST http://api.test/api/v1/admin/doctors/d%201/reject",
    ]);
    expect(JSON.parse(calls[2][1].body as string)).toEqual({ reason: "Not on the register" });
  });

  it("uploads documents as multipart form data without a JSON content type", async () => {
    const fetchImpl = fakeFetch(201, { id: "d1" });
    const api = createApiClient({ baseUrl: "http://api.test", getToken: () => "t", fetchImpl });
    const file = new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "r.pdf", { type: "application/pdf" });
    await api.patient.uploadDocument({ file, documentType: "lab_report", sourceLanguage: "ta" });
    const init = fetchImpl.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("document_type")).toBe("lab_report");
    expect((init.body as FormData).get("source_language")).toBe("ta");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });
});
