/**
 * IP-SAKTI's UI kit (Phase 3.5). Each piece carries its meaning in words and
 * structure, never colour alone, and uses real form controls under its styling.
 */
import { lookup } from "@carebridge/i18n";
import { saktiCatalogs } from "@carebridge/i18n/catalogs";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderSakti } from "@/test/utils";
import { ChoiceCard, DemoTag, LaneMark, ReadinessItem, StateBadge, StepProgress, laneRule, type ProductState } from ".";

const en = (key: string) => lookup(saktiCatalogs.en, key)!;

describe("the UI kit", () => {
  it.each(["not_classified", "in_progress", "requires_information", "awaiting_confirmation", "confirmed"] as ProductState[])(
    "names the %s state in words, with an icon",
    (state) => {
      renderSakti(<StateBadge state={state} />);
      const badge = screen.getByText(en(`ui.state.${state}`));
      expect(badge.querySelector("svg")).not.toBeNull();
    },
  );

  it("tells the lanes apart by name, icon and rule, not hue alone", () => {
    renderSakti(
      <>
        <LaneMark lane="india" />
        <LaneMark lane="international" />
      </>,
    );
    expect(screen.getByText(en("ui.lane.india")).querySelector("svg")).not.toBeNull();
    expect(screen.getByText(en("ui.lane.international")).querySelector("svg")).not.toBeNull();
    expect(laneRule("india")).not.toContain("double");
    expect(laneRule("international")).toContain("double");
  });

  it("labels demo data in words", () => {
    renderSakti(<DemoTag />);
    expect(screen.getByText(en("ui.demo.tag"))).toBeInTheDocument();
  });

  it("reports progress as a labelled progress bar", () => {
    renderSakti(<StepProgress step={2} total={4} label="Step 2 of 4" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "4");
    expect(bar).toHaveAttribute("aria-valuetext", "Step 2 of 4");
  });

  it("makes an answer card a real, keyboard-operable radio", async () => {
    const onChange = vi.fn();
    renderSakti(
      <div>
        <ChoiceCard name="q" value="yes" checked={false} onChange={onChange} title="Yes" hint="A hint" />
        <ChoiceCard name="q" value="unknown" checked={false} onChange={onChange} title="I don't know" kind="unknown" />
      </div>,
    );
    const yes = screen.getByRole("radio", { name: /Yes/ });
    yes.focus();
    await userEvent.keyboard(" ");
    expect(onChange).toHaveBeenCalledWith("yes");
    await userEvent.click(screen.getByText("I don't know"));
    expect(onChange).toHaveBeenCalledWith("unknown");
  });

  it("says whether a readiness item is ready to a screen reader, not only by icon", () => {
    renderSakti(
      <ul>
        <ReadinessItem done label="Ready thing" />
        <ReadinessItem done={false} label="Pending thing" />
      </ul>,
    );
    expect(screen.getByText("Ready thing").textContent).toContain(en("ui.readiness.done"));
    expect(screen.getByText("Pending thing").textContent).toContain(en("ui.readiness.notYet"));
  });
});
