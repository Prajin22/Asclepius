import { I18nProvider } from "@carebridge/i18n";
import { patientCatalogs } from "@carebridge/i18n/catalogs";
import type { Message, Prescription } from "@carebridge/shared-types";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  LanguageTag,
  MessageThread,
  PageImage,
  PrescriptionCard,
  ReadingProvenance,
  SourceBadge,
  StatusBadge,
  readingWarningKey,
} from "../src";

function wrap(ui: ReactNode, locale = "en") {
  return render(
    <I18nProvider locale={locale} catalogs={patientCatalogs}>
      {ui}
    </I18nProvider>,
  );
}

const rx: Prescription = {
  id: "rx1",
  consultation_id: "c1",
  authorship: "doctor",
  authored_by: { id: "d1", name: "Dr. Meera Sharma", specialization: "General Medicine", registration_identifier: "DEMO-1" },
  instructions: "Rest well.",
  created_at: "2026-09-10T10:00:00Z",
  items: [
    { position: 1, medication: "Paracetamol 500 mg", dosage: "1 tablet", frequency: "Twice daily", duration: "3 days", instructions: "After food" },
  ],
};

describe("SourceBadge", () => {
  it("labels each source distinctly", () => {
    wrap(
      <>
        <SourceBadge source="patient" />
        <SourceBadge source="ai_extracted" />
        <SourceBadge source="doctor" />
      </>,
    );
    expect(screen.getByText("Patient provided")).toBeInTheDocument();
    expect(screen.getByText("AI extracted")).toBeInTheDocument();
    expect(screen.getByText("Doctor provided")).toBeInTheDocument();
  });

  it("is localised", () => {
    wrap(<SourceBadge source="doctor" />, "ta");
    expect(screen.getByText("மருத்துவர் வழங்கியது")).toBeInTheDocument();
  });
});

describe("StatusBadge / LanguageTag", () => {
  it("shows status text", () => {
    wrap(<StatusBadge status="active" />, "hi");
    expect(screen.getByText("सक्रिय")).toBeInTheDocument();
  });
  it("renders autonym with lang attribute", () => {
    wrap(<LanguageTag code="ta" />);
    expect(screen.getByText("தமிழ்")).toHaveAttribute("lang", "ta");
  });
});

describe("PrescriptionCard", () => {
  it("keeps doctor attribution and items exactly as written", () => {
    wrap(<PrescriptionCard prescription={rx} />);
    expect(screen.getByText("Dr. Meera Sharma")).toBeInTheDocument();
    expect(screen.getByText("Written by the doctor")).toBeInTheDocument();
    expect(screen.getByText("Paracetamol 500 mg")).toBeInTheDocument();
    expect(screen.getByText("Twice daily")).toBeInTheDocument();
    expect(screen.getByText("Rest well.")).toBeInTheDocument();
    expect(screen.getByText(/DEMO-1/)).toBeInTheDocument();
  });
});

describe("ReadingProvenance", () => {
  it("labels an exact copy differently from a machine transcription", () => {
    wrap(
      <>
        <ReadingProvenance method="pdf_text_layer" engine="pdfplumber" confidence={null} />
        <ReadingProvenance method="ocr" engine="rapidocr" confidence={0.634} warnings={["low_ocr_confidence"]} />
      </>,
    );
    expect(screen.getByText("Copied exactly from the PDF")).toBeInTheDocument();
    expect(screen.getByText(/Read by OCR — machine transcription/)).toBeInTheDocument();
    expect(screen.getByText(/hard to read/)).toBeInTheDocument();
    // Confidence and engine are developer material: present, but behind the disclosure.
    expect(screen.getAllByText("Technical details")).toHaveLength(2);
    expect(screen.getByText(/OCR confidence 63%/)).toBeInTheDocument();
  });

  it("maps warning codes, including provider failures", () => {
    expect(readingWarningKey("vision_failed:ai_timeout")).toBe("reading.warnings.failed");
    expect(readingWarningKey("only_first_10_of_12_pages_processed")).toBeNull();
  });
});

describe("PageImage", () => {
  beforeAll(() => {
    Object.assign(URL, { createObjectURL: vi.fn(() => "blob:page"), revokeObjectURL: vi.fn() });
  });

  it("shows the original page with evidence outlined as an overlay", async () => {
    wrap(
      <PageImage
        load={async () => new Blob(["png"])}
        page={2}
        regions={[
          { id: "a", bbox: [0.1, 0.2, 0.5, 0.25], active: true },
          { id: "b", bbox: [0.1, 0.3, 0.5, 0.35] },
        ]}
      />,
    );
    expect(await screen.findByAltText("Page 2 of the original document")).toHaveAttribute("src", "blob:page");
    const [active, other] = screen.getAllByTestId("evidence-region");
    expect(active).toHaveAttribute("data-active", "true");
    expect(other).toHaveAttribute("data-active", "false");
    expect(active.style.left).toBe("9.6%");
  });
});

describe("MessageThread", () => {
  const messages: Message[] = [
    { id: "m1", sender_role: "patient", body: "வணக்கம் டாக்டர்", language: "ta", created_at: "2026-09-10T10:00:00Z" },
    { id: "m2", sender_role: "doctor", body: "Hello", language: "en", created_at: "2026-09-10T10:05:00Z" },
  ];

  it("shows messages with original language and sends new ones", async () => {
    const onSend = vi.fn(async () => {});
    wrap(<MessageThread messages={messages} viewerRole="patient" canSend onSend={onSend} />);
    expect(screen.getByText("வணக்கம் டாக்டர்")).toHaveAttribute("lang", "ta");
    await userEvent.type(screen.getByLabelText("Message"), "Thank you");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Thank you");
  });

  it("explains when messaging is closed", () => {
    wrap(<MessageThread messages={[]} viewerRole="patient" canSend={false} onSend={vi.fn()} />);
    expect(screen.getByText(/available while the consultation is active/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });

  it("shows a localised error when sending fails", async () => {
    const onSend = vi.fn(async () => {
      throw { code: "invalid_transition" };
    });
    wrap(<MessageThread messages={[]} viewerRole="doctor" canSend onSend={onSend} />);
    await userEvent.type(screen.getByLabelText("Message"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not possible at this stage");
  });
});
