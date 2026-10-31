import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { pct } from "@/components/ui/stat";
import { EligibilityBadge, VerificationBadge } from "@/components/ui/status";
import { BarList } from "./bar-list";
import { RadarChart, readinessAxes } from "./radar";

describe("RadarChart", () => {
  it("labels every dimension with its value, as text and for assistive tech", () => {
    render(
      <RadarChart
        title="Readiness"
        axes={readinessAxes({ technical: 80, aptitude: 60, communication: 55, project_depth: 30 })}
      />,
    );
    expect(screen.getByRole("img", { name: "Readiness" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Technical mastery: 80%" })).toBeTruthy();
    expect(screen.getAllByText("Project depth").length).toBeGreaterThan(0);
    expect(screen.getByText("30%")).toBeTruthy();
  });
});

describe("BarList", () => {
  it("shows values as text and clamps widths", () => {
    const { container } = render(<BarList title="Supply" rows={[{ key: 1, label: "Django", value: 140 }]} />);
    expect(screen.getByText("140%")).toBeTruthy();
    const bar = container.querySelector(".bg-series-1") as HTMLElement;
    expect(bar.style.width).toBe("100%");
  });
});

describe("status badges", () => {
  it("never rely on colour alone", () => {
    render(
      <>
        <VerificationBadge status="verified" />
        <EligibilityBadge eligible={false} />
        <EligibilityBadge eligible={null} />
      </>,
    );
    expect(screen.getByText("Verified")).toBeTruthy();
    expect(screen.getByText("Not eligible")).toBeTruthy();
    expect(screen.getByText("Not evaluated")).toBeTruthy();
  });

  it("formats missing numbers as a dash, never a made-up value", () => {
    expect(pct(null)).toBe("—");
    expect(pct(72.4)).toBe("72%");
  });
});
