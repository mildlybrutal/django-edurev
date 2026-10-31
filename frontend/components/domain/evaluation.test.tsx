import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Evaluation } from "@/lib/api/types";
import { EligibilityCard, EvaluationView, GapList } from "./evaluation";

const base: Evaluation = {
  drive_id: 1,
  eligibility: {
    is_eligible: false,
    computed_at: "2026-10-21T00:00:00Z",
    reasons: [
      { rule: "min_cgpa", passed: false, required: "CGPA ≥ 7.5", actual: "6.80", message: "CGPA 6.80 is below 7.5" },
      {
        rule: "max_active_backlogs",
        passed: true,
        required: "No active backlogs",
        actual: "0",
        message: "Backlog requirement met",
      },
    ],
  },
  compatibility: {
    score: 88,
    computed_at: "2026-10-21T00:00:00Z",
    requirements: [
      {
        skill_id: 1,
        skill: "Frontend Framework",
        required_level: 2,
        required_label: "Intermediate",
        weight: 2,
        is_mandatory: true,
        match: "taxonomy",
        matched_skill: "React",
        level: 3,
        level_label: "Advanced",
        verified_level: 3,
        verified_label: "Advanced",
        credit: 1,
      },
    ],
  },
  readiness: null,
  is_ready: false,
  ready_threshold: 70,
  gaps: [],
  registration: null,
  registration_open: true,
  plan_id: null,
};

describe("EvaluationView", () => {
  it("keeps eligibility and skill compatibility in separate cards", () => {
    render(<EvaluationView evaluation={base} />);
    const eligibility = screen.getByRole("heading", { name: "Eligibility" }).closest("section")!;
    const compatibility = screen.getByRole("heading", { name: "Skill compatibility" }).closest("section")!;
    expect(eligibility).not.toBe(compatibility);
    // A strong skill match does not make an ineligible student look eligible, and vice versa.
    expect(within(eligibility).getByText("Not eligible")).toBeTruthy();
    expect(within(eligibility).queryByText("88%")).toBeNull();
    expect(within(compatibility).getByText("88%")).toBeTruthy();
  });

  it("explains taxonomy-expanded matches", () => {
    render(<EvaluationView evaluation={base} />);
    expect(screen.getByText("via React")).toBeTruthy();
  });

  it("lists every failed and passed criterion", () => {
    render(<EligibilityCard evaluation={base} />);
    expect(screen.getByText(/CGPA 6.80 is below 7.5/)).toBeTruthy();
    expect(screen.getByText("No active backlogs")).toBeTruthy();
  });
});

describe("GapList", () => {
  it("shows ranked, actionable gaps", () => {
    render(
      <GapList
        gaps={[
          {
            rank: 1,
            skill_id: 2,
            skill: "Docker",
            kind: "below_level",
            kind_label: "Below required level",
            current: "Beginner",
            verified: "Beginner",
            required: "Intermediate",
            is_mandatory: true,
            impact: "high",
            impact_score: 3,
            suggested_action: "Take Docker from Beginner to Intermediate.",
          },
        ]}
      />,
    );
    expect(screen.getByText("Rank 1:")).toBeTruthy();
    expect(screen.getByText("High impact")).toBeTruthy();
    expect(screen.getByText("Take Docker from Beginner to Intermediate.")).toBeTruthy();
  });

  it("marks only the top gap as the next step, and only for the student", () => {
    const gaps = [1, 2].map((rank) => ({
      rank,
      skill_id: rank,
      skill: `Skill ${rank}`,
      kind: "missing" as const,
      kind_label: "Missing",
      current: "None",
      verified: "None",
      required: "Intermediate",
      is_mandatory: false,
      impact: "medium" as const,
      impact_score: 1,
      suggested_action: "Learn it.",
      cluster: "testing",
    }));
    const { unmount } = render(<GapList gaps={gaps} showNext />);
    expect(screen.getAllByText("Start here")).toHaveLength(1);
    unmount();
    render(<GapList gaps={gaps} />);
    expect(screen.queryByText("Start here")).toBeNull();
  });

  it("says so when there are no gaps", () => {
    render(<GapList gaps={[]} />);
    expect(screen.getByText("No gaps")).toBeTruthy();
  });
});
