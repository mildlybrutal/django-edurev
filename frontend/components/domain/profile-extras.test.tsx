import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ThemeSwitch } from "@/components/shell/theme-switch";
import { handleFrom, resumeProblem } from "@/lib/api/profile-extras";
import { hueFor } from "@/lib/modules";
import { TimeBudget } from "./time-budget";

describe("handleFrom", () => {
  it("reduces pasted links and @handles to the username", () => {
    expect(handleFrom("https://github.com/ada-lovelace", "github.com")).toBe("ada-lovelace");
    expect(handleFrom("github.com/ada-lovelace/repo", "github.com")).toBe("ada-lovelace");
    expect(handleFrom("@ada", "github.com")).toBe("ada");
    expect(handleFrom("https://leetcode.com/u/ada_codes/", "leetcode.com")).toBe("ada_codes");
    expect(handleFrom("https://leetcode.com/ada_codes", "leetcode.com")).toBe("ada_codes");
    expect(handleFrom("  ada  ", "leetcode.com")).toBe("ada");
  });
});

describe("resumeProblem", () => {
  it("rejects non-PDFs and files over 5 MB before upload", () => {
    expect(resumeProblem(new File(["x"], "cv.docx"))).toMatch(/PDF/);
    const big = new File(["x"], "cv.pdf");
    Object.defineProperty(big, "size", { value: 6 * 1024 * 1024 });
    expect(resumeProblem(big)).toMatch(/5 MB/);
    expect(resumeProblem(new File(["%PDF-1.4"], "cv.pdf"))).toBeNull();
  });
});

describe("hueFor", () => {
  it("maps seeded clusters to their module hue and others to a stable hue", () => {
    expect(hueFor("databases")).toBe("teal");
    expect(hueFor("testing")).toBe("marigold");
    expect(hueFor("cs-fundamentals")).toBe("crimson");
    expect(hueFor(null)).toBe("cobalt");
    expect(hueFor("custom-cluster")).toBe(hueFor("custom-cluster"));
  });
});

describe("TimeBudget", () => {
  afterEach(() => vi.useRealTimers());

  it("flags a plan whose time runs ahead of the work", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-21T12:00:00Z"));
    render(
      <TimeBudget start="2026-10-01" end="2026-10-31" driveDate="2026-10-31" done={1} total={10} company="Acme" />,
    );
    expect(screen.getByText("10 days left")).toBeTruthy();
    expect(screen.getByText(/Behind schedule/)).toBeTruthy();
  });

  it("does not flag a plan on track", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-21T12:00:00Z"));
    render(<TimeBudget start="2026-10-01" end="2026-10-31" done={8} total={10} />);
    expect(screen.queryByText(/Behind schedule/)).toBeNull();
  });
});

describe("ThemeSwitch", () => {
  afterEach(() => {
    document.documentElement.removeAttribute("data-theme");
    localStorage.clear();
  });

  it("is a radio group that applies and remembers the theme", () => {
    render(<ThemeSwitch />);
    expect(screen.getByRole("radio", { name: "System" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(screen.getByRole("radio", { name: "Dark" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem("theme")).toBeNull();
  });
});
