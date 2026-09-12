import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithI18n } from "@/test/utils";
import { PrescriptionForm, validateItems } from "./PrescriptionForm";

describe("validateItems", () => {
  it("flags every missing required field per item", () => {
    expect(
      validateItems([
        { medication: "Paracetamol", dosage: "1 tab", frequency: "BD", duration: "3 days" },
        { medication: " ", dosage: "", frequency: "OD", duration: "" },
      ]),
    ).toEqual({ 1: ["medication", "dosage", "duration"] });
  });
});

describe("PrescriptionForm", () => {
  it("does not submit incomplete items", async () => {
    const onSubmit = vi.fn();
    renderWithI18n(<PrescriptionForm onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Issue prescription" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getAllByText("Required")).toHaveLength(4);
  });

  it("submits exactly what the doctor typed, for multiple medicines", async () => {
    const onSubmit = vi.fn(async () => {});
    renderWithI18n(<PrescriptionForm onSubmit={onSubmit} />);
    const fill = async (index: number, values: string[]) => {
      const labels = ["Medication", "Dosage", "Frequency", "Duration"];
      for (const [i, label] of labels.entries()) {
        await userEvent.type(screen.getAllByLabelText(label)[index], values[i]);
      }
    };
    await fill(0, ["Paracetamol 500 mg", "1 tablet", "Twice daily", "3 days"]);
    await userEvent.click(screen.getByRole("button", { name: "Add another medicine" }));
    await fill(1, ["ORS", "1 sachet", "After each loose stool", "2 days"]);
    await userEvent.type(screen.getByLabelText("General instructions (optional)"), "Drink fluids.");
    await userEvent.click(screen.getByRole("button", { name: "Issue prescription" }));

    expect(onSubmit).toHaveBeenCalledWith({
      items: [
        { medication: "Paracetamol 500 mg", dosage: "1 tablet", frequency: "Twice daily", duration: "3 days", instructions: null },
        { medication: "ORS", dosage: "1 sachet", frequency: "After each loose stool", duration: "2 days", instructions: null },
      ],
      instructions: "Drink fluids.",
    });
    expect(await screen.findByText("Prescription issued.")).toBeInTheDocument();
  });

  it("can remove an added medicine", async () => {
    renderWithI18n(<PrescriptionForm onSubmit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Add another medicine" }));
    expect(screen.getByText("Medicine 2")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
    expect(screen.queryByText("Medicine 2")).not.toBeInTheDocument();
  });
});
