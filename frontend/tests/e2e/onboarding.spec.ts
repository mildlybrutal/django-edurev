import { expect, test } from "@playwright/test";

const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");

/** Self sign-up → onboarding pop-up → LinkedIn + resume saved → resume viewable → pop-up gone. */
test("student signs up and completes the onboarding pop-up", async ({ page }) => {
  const stamp = Date.now().toString().slice(-7);
  const regNo = `9${stamp}`; // 8 digits, outside the demo range 1230xxxx
  await page.goto("/signup");
  await page.getByLabel("First name").fill("Onboarding");
  await page.getByLabel("Last name").fill(`Tester ${stamp}`);
  await page.getByLabel("College email").fill(`onboard.${stamp}@example.test`);
  await page.getByLabel("Password").fill("Sturdy-Pass-2026");
  await page.getByLabel("Registration number").fill(regNo);
  await page.getByLabel("Department").selectOption({ index: 1 });
  await page.getByLabel("Current CGPA").fill("8.1");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/student$/);

  const dialog = page.getByRole("dialog", { name: "Complete your placement profile" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("LinkedIn profile link").fill(`https://www.linkedin.com/in/onboarding-${stamp}`);
  await dialog
    .locator('input[type="file"]')
    .setInputFiles({ name: "resume.pdf", mimeType: "application/pdf", buffer: PDF });
  await dialog.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Profile set up" })).toBeVisible();
  await expect(dialog).toBeHidden();

  await page.goto("/student/profile");
  await expect(page.getByText("Awaiting confirmation")).toBeVisible();
  await expect(page.getByText("resume.pdf")).toBeVisible();
  await page.getByRole("button", { name: "View resume" }).click();
  await expect(page.locator('iframe[title="Resume PDF"]')).toBeVisible();

  await page.reload();
  await expect(page.getByRole("dialog", { name: "Complete your placement profile" })).toBeHidden();
});
