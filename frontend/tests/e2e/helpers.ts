import { expect, type Browser, type Page } from "@playwright/test";

export const PASSWORD = process.env.E2E_PASSWORD ?? "Demo-Pass-2026";

export const USERS = {
  student: "student@demo.example.test",
  faculty: "faculty@demo.example.test",
  officer: "placement.officer@demo.example.test",
  head: "placement.head@demo.example.test",
  recruiter: "recruiter@demo.example.test",
};

/** A fresh browser context (own cookies) signed in as `email`. */
export async function signIn(
  browser: Browser,
  email: string,
  portal: "internal" | "recruiter" = "internal",
): Promise<Page> {
  const context = await browser.newContext();
  // The first-run onboarding pop-up is covered by onboarding.spec.ts; journeys skip it ("Later").
  await context.addInitScript(() => sessionStorage.setItem("onboarding-later", "1"));
  const page = await context.newPage();
  await page.goto(portal === "recruiter" ? "/recruiter/login" : "/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  return page;
}

/** Reload `page` until `check` passes (for results produced by the background worker). */
export async function eventually(page: Page, check: () => Promise<void>, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      await check();
      return;
    } catch (error) {
      if (Date.now() > deadline) throw error;
      await page.waitForTimeout(2_000);
      await page.reload();
    }
  }
}
