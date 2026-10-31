import { expect, test } from "@playwright/test";
import { eventually, signIn, USERS } from "./helpers";

/**
 * The P06 §15 end-to-end journey: evidence added → verified → profile updates → drive published
 * → gap analysis → preparation plan → recruiter views the shortlist, plus the negative recruiter case.
 */
test("evidence to recruiter shortlist", async ({ browser }) => {
  const stamp = Date.now().toString().slice(-6);
  const evidenceTitle = `E2E task queue project ${stamp}`;
  const company = `E2E Corp ${stamp}`;

  // 1. Student adds evidence and asks for verification.
  const student = await signIn(browser, USERS.student);
  const me = await (await student.request.get("/api/v1/auth/me/")).json();
  const studentName = `${me.first_name} ${me.last_name}`.trim();
  await student.goto("/student/evidence");
  await student.getByLabel("Title").fill(evidenceTitle);
  await student.getByPlaceholder("Add a skill…").fill("Celery");
  await student.getByRole("button", { name: /^Celery/ }).click();
  await student.getByRole("button", { name: "Add evidence" }).click();
  const item = student.locator("li", { hasText: evidenceTitle });
  await expect(item.getByText("Pending")).toBeVisible();

  // 2. The mentor verifies it.
  const faculty = await signIn(browser, USERS.faculty);
  await faculty.goto("/faculty/verification");
  const card = faculty.locator("section", { has: faculty.getByRole("heading", { name: evidenceTitle }) });
  await card.getByRole("button", { name: "Verify" }).click();
  await expect(faculty.getByRole("heading", { name: evidenceTitle })).toHaveCount(0);

  // 3. The student's profile updates (debounced recompute on the worker).
  await student.goto("/student/profile");
  await eventually(student, async () => {
    const claim = student.getByRole("button", { name: /Celery/ });
    await expect(claim).toBeVisible({ timeout: 3_000 });
    await expect(claim.getByText("Verified", { exact: true })).toBeVisible({ timeout: 3_000 });
  });

  // 4. The placement officer creates a drive from a pasted JD and publishes it.
  const officer = await signIn(browser, USERS.officer);
  await officer.goto("/placement/drives");
  await officer.getByRole("button", { name: "New drive" }).click();
  await officer.getByLabel("New company name").fill(company);
  await officer.getByLabel("Role title").fill("Backend Engineer");
  await officer.getByRole("button", { name: "Create draft drive" }).click();
  await expect(officer).toHaveURL(/\/placement\/drives\/\d+$/);
  const drivePath = new URL(officer.url()).pathname;
  const driveId = drivePath.split("/").pop();
  await officer.getByRole("tab", { name: "Job description" }).click();
  await officer
    .getByLabel("Job description")
    .fill(
      "Backend Engineer. Must have strong Python and Django. Experience with Celery is required.\n" +
        "Solid System Design and Performance Testing are essential.\n\nEligibility: minimum 7.0 CGPA, no active backlogs.",
    );
  await officer.getByRole("button", { name: "Process JD" }).click();
  await officer.getByRole("button", { name: "Apply to drive" }).click();
  await officer.getByRole("tab", { name: "Requirements & eligibility" }).click();
  await expect(officer.getByRole("cell", { name: /^Celery/ })).toBeVisible();
  await officer.getByRole("button", { name: "Publish (opens registration)" }).click();
  await expect(officer.getByText("Published (registration open)").first()).toBeVisible();

  // 5. The student sees eligibility and readiness separately, the ranked gaps, registers and plans.
  await student.goto(`/student/drives/${driveId}`);
  await expect(student.getByRole("heading", { name: "Eligibility" })).toBeVisible();
  await expect(student.getByRole("heading", { name: "Skill compatibility" })).toBeVisible();
  await expect(student.getByRole("heading", { name: "Readiness for this role" })).toBeVisible();
  await expect(student.getByRole("heading", { name: "Skill gaps" })).toBeVisible();
  await expect(student.getByText("Eligible", { exact: true }).first()).toBeVisible();
  await student.getByRole("button", { name: "Register" }).click();
  await expect(student.getByText("Registered", { exact: true })).toBeVisible();
  await student.getByRole("button", { name: "Create a preparation plan from these gaps" }).click();
  await expect(student).toHaveURL(/\/student\/plan\?plan=\d+/);
  await expect(student.getByRole("heading", { name: "Calendar" })).toBeVisible();
  await expect(student.getByText(/Checkpoint:/).first()).toBeVisible();

  // 6. The officer closes registration and shortlists the student.
  await officer.goto(drivePath);
  await officer.getByRole("button", { name: "Close registration" }).click();
  await expect(officer.getByText("Registration closed").first()).toBeVisible();
  await officer.getByRole("tab", { name: "Matching & shortlist" }).click();
  await eventually(officer, async () => {
    await officer.getByRole("tab", { name: "Matching & shortlist" }).click({ timeout: 3_000 });
    await expect(officer.getByLabel(`Decision for ${studentName}`)).toBeVisible({ timeout: 3_000 });
  });
  await officer.getByLabel(`Decision for ${studentName}`).selectOption("shortlisted");
  await expect(
    officer.getByRole("row", { name: new RegExp(studentName) }).getByText("Shortlisted", { exact: true }),
  ).toBeVisible();

  // 7. The placement head grants the recruiter access to the shortlist.
  const head = await signIn(browser, USERS.head);
  await head.goto("/placement/recruiter-access");
  await head.getByLabel("Recruiter", { exact: true }).selectOption({ label: USERS.recruiter });
  await head.getByLabel("Drive", { exact: true }).selectOption({ label: `${company} — Backend Engineer` });
  await head.getByLabel("Candidates", { exact: true }).selectOption("shortlisted");
  const tomorrow = new Date(Date.now() + 86_400_000);
  const local = new Date(tomorrow.getTime() - tomorrow.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  await head.getByLabel("Expires", { exact: true }).fill(local);
  await head.getByRole("button", { name: "Grant access" }).click();
  await expect(head.getByRole("cell", { name: `${company} — Backend Engineer` })).toBeVisible();

  // 8. The recruiter sees the shortlisted student, and nothing for drives without a grant.
  const recruiter = await signIn(browser, USERS.recruiter, "recruiter");
  await recruiter.goto(`/recruiter/drives/${driveId}`);
  await expect(recruiter.getByRole("button", { name: studentName })).toBeVisible();
  await expect(recruiter.getByText("1 candidates")).toBeVisible();
  await recruiter.goto("/recruiter/drives/999999");
  await expect(recruiter.getByText(/not found/i)).toBeVisible();

  // 9. The access is logged and reviewable by the head.
  await head.goto("/placement/recruiter-access");
  await expect(head.getByRole("cell", { name: "Denied" }).first()).toBeVisible();
});
