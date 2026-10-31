import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { signIn, USERS } from "./helpers";

/** CES §1.5: zero critical axe violations on student-facing pages (we also hold "serious" to zero). */
const STUDENT_PAGES = [
  "/student",
  "/student/profile",
  "/student/evidence",
  "/student/drives",
  "/student/assessments",
  "/student/plan",
  "/student/progress",
  "/account",
];

async function critical(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations
    .filter((v) => v.impact === "critical" || v.impact === "serious")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}

test("login page has no critical accessibility violations", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  expect(await critical(page)).toEqual([]);
});

test("student pages have no critical accessibility violations", async ({ browser }) => {
  const page = await signIn(browser, USERS.student);
  for (const path of STUDENT_PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await critical(page), path).toEqual([]);
  }
});

test("dark theme, sign-up and staff pages have no critical accessibility violations", async ({ browser }) => {
  const student = await signIn(browser, USERS.student);
  await student.context().addInitScript(() => localStorage.setItem("theme", "dark"));
  for (const path of ["/student", "/student/profile", "/student/plan"]) {
    await student.goto(path);
    await expect(student.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(student.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await critical(student), `dark ${path}`).toEqual([]);
  }
  await student.goto("/signup");
  await expect(student.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await critical(student), "dark /signup").toEqual([]);

  const officer = await signIn(browser, USERS.officer);
  for (const path of ["/placement", "/placement/students"]) {
    await officer.goto(path);
    await expect(officer.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await critical(officer), path).toEqual([]);
  }
});
