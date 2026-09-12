import type { MedicalDocument } from "@carebridge/shared-types";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "@/test/utils";
import { UploadForm, validateFile } from "./UploadForm";

const pdf = () => new File([new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])], "report.pdf", { type: "application/pdf" });

const uploaded: MedicalDocument = {
  id: "d1",
  file_name: "report.pdf",
  mime_type: "application/pdf",
  size_bytes: 5,
  document_type: "lab_report",
  title: null,
  source_language: null,
  status: "uploaded",
  uploaded_at: "2026-09-12T00:00:00Z",
};

function chooseFile(file: File, label = "File") {
  fireEvent.change(screen.getByLabelText(label), { target: { files: [file] } });
}

describe("validateFile", () => {
  it("accepts PDFs and images, rejects executables, empty and oversized files", () => {
    expect(validateFile(pdf())).toBeNull();
    expect(validateFile(new File(["x"], "a.png", { type: "image/png" }))).toBeNull();
    expect(validateFile(new File(["MZ"], "setup.exe", { type: "application/x-msdownload" }))).toBe("errors.unsupported_type");
    expect(validateFile(new File([], "e.pdf", { type: "application/pdf" }))).toBe("errors.empty_file");
    const big = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "big.pdf", { type: "application/pdf" });
    expect(validateFile(big)).toBe("errors.file_too_large");
    expect(validateFile(null)).toBe("documents.fileRequired");
  });
});

describe("UploadForm", () => {
  it("requires a file and a document type before uploading", async () => {
    const upload = vi.fn();
    renderWithI18n(<UploadForm upload={upload} />);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(screen.getByText("Please choose a file.")).toBeInTheDocument();
    expect(screen.getByText("Please select a document type.")).toBeInTheDocument();
    expect(upload).not.toHaveBeenCalled();
  });

  it("rejects an executable immediately", () => {
    renderWithI18n(<UploadForm upload={vi.fn()} />);
    chooseFile(new File(["MZ"], "setup.exe", { type: "application/x-msdownload" }));
    expect(screen.getByText("Only PDF, JPEG, PNG or WEBP files can be uploaded.")).toBeInTheDocument();
  });

  it("uploads with the chosen type and explains how to have it read", async () => {
    const upload = vi.fn(async () => uploaded);
    const onUploaded = vi.fn();
    renderWithI18n(<UploadForm upload={upload} onUploaded={onUploaded} />);
    chooseFile(pdf());
    await userEvent.selectOptions(screen.getByLabelText("Document type"), "lab_report");
    await userEvent.type(screen.getByLabelText("Short title (optional)"), "Lipid profile");
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(upload).toHaveBeenCalledWith(
      expect.objectContaining({ documentType: "lab_report", title: "Lipid profile", sourceLanguage: null }),
    );
    expect(await screen.findByText("Open a document to have its text read and review what was found.")).toBeInTheDocument();
    expect(onUploaded).toHaveBeenCalledWith(uploaded);
  });

  it("shows a localised server error", async () => {
    const upload = vi.fn(async () => {
      throw { code: "content_mismatch" };
    });
    renderWithI18n(<UploadForm upload={upload} />, "ta");
    chooseFile(pdf(), "கோப்பு");
    await userEvent.selectOptions(screen.getByLabelText("ஆவண வகை"), "scan");
    await userEvent.click(screen.getByRole("button", { name: "பதிவேற்று" }));
    expect(await screen.findByText("இந்தக் கோப்பின் உள்ளடக்கம் அதன் வகையுடன் பொருந்தவில்லை.")).toBeInTheDocument();
  });
});
