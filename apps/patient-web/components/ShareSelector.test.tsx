import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { emptySelection, type SelectionState, type ShareItem } from "@/lib/sharing";
import { renderWithI18n } from "@/test/utils";
import { ShareSelector } from "./ShareSelector";
import type { ShareCategory } from "@carebridge/shared-types";

const items: Record<ShareCategory, ShareItem[]> = {
  current_problem: [{ id: "p1", label: "Headache for three days" }],
  medical_history: [
    { id: "h1", label: "Hypertension" },
    { id: "h2", label: "Penicillin allergy" },
  ],
  documents: [{ id: "d1", label: "Lipid profile" }],
  previous_consultations: [],
  previous_prescriptions: [{ id: "rx1", label: "Dr. Rajesh Iyer · Apr 2026" }],
};

let latest: SelectionState = emptySelection();

function Harness({ initial }: { initial: SelectionState }) {
  const [value, setValue] = useState(initial);
  latest = value;
  return (
    <ShareSelector
      items={items}
      value={value}
      onChange={(v) => {
        latest = v;
        setValue(v);
      }}
    />
  );
}

describe("ShareSelector", () => {
  it("renders every category, with an empty-state for categories without items", () => {
    renderWithI18n(<Harness initial={emptySelection()} />);
    expect(screen.getByText("Current problem")).toBeInTheDocument();
    expect(screen.getByText("Relevant medical history")).toBeInTheDocument();
    expect(screen.getByText("Previous consultations")).toBeInTheDocument();
    expect(screen.getByText("Nothing to share in this category.")).toBeInTheDocument();
  });

  it("category checkbox selects and clears all of its items", async () => {
    renderWithI18n(<Harness initial={emptySelection()} />);
    const category = screen.getByRole("checkbox", { name: /Relevant medical history/ });
    await userEvent.click(category);
    expect(latest.medical_history.sort()).toEqual(["h1", "h2"]);
    await userEvent.click(category);
    expect(latest.medical_history).toEqual([]);
  });

  it("individual items can be unticked, leaving the category partially selected", async () => {
    renderWithI18n(<Harness initial={{ ...emptySelection(), medical_history: ["h1", "h2"] }} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /Penicillin allergy/ }));
    expect(latest.medical_history).toEqual(["h1"]);
    const category = screen.getByRole("checkbox", { name: /Relevant medical history/ }) as HTMLInputElement;
    expect(category.indeterminate).toBe(true);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("previous prescriptions start unshared and can be opted in", async () => {
    renderWithI18n(<Harness initial={emptySelection()} />);
    const rx = screen.getByRole("checkbox", { name: /Dr. Rajesh Iyer/ });
    expect(rx).not.toBeChecked();
    await userEvent.click(rx);
    expect(latest.previous_prescriptions).toEqual(["rx1"]);
  });
});
