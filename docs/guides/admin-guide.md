# Administrator guide

## Accounts and roles

- Django admin (`/admin/`) is for platform superusers. Create the **Institution**, then users. Each user needs an institution and one role group: `student`, `faculty`, `placement_officer`, `placement_head`, `recruiter` or `admin`.
- Students are normally created by the placement cell (**Placement → Students → Add student**) or imported. Their academic record (CGPA, backlogs, department, graduation year, mentor) is maintained there and is read-only to students.
- Recruiter accounts are created by the placement head under **Recruiter Access**.
- In production, admin, placement head and officer accounts must enrol TOTP two-factor authentication (`MFA_REQUIRED_ROLES`). A user who loses their authenticator: a superuser deletes their **TOTP device** row in Django admin, and the user enrols again at next sign-in.

## Skill taxonomy (**Placement → Manage Skills**)

The taxonomy is the vocabulary for matching.

- **Skills and categories:** add skills, and mark categories such as "Frontend Framework" as *Category*.
- **Synonyms:** add synonyms ("Postgres" for PostgreSQL). A name can be a skill or a synonym, not both.
- **"Satisfies" links:** link a skill to the broader skills it satisfies (React → Frontend Framework). Cycles are refused.
- **Merge:** merge duplicates. The merged name becomes a synonym, and evidence, roles and links move over.
- **Retire:** retire skills rather than deleting them.
- **Target roles:** the starter roles (Software Development Engineer, Data Analyst, QA / Test Engineer) can be edited, and new roles added. They are templates for drive requirements.

All changes are audited.

## Scoring (**Placement → Scoring & Rubrics**)

- **Readiness model:**
  - dimension weights
  - unverified-evidence credit
  - assessment window
  - project target
  - "ready" threshold

  Publishing creates a new version: existing snapshots keep the version that produced them. Run **Batch Analytics → Recompute** to apply it to everyone.
- **Evidence rules:** the highest level each evidence type can establish, verified and unverified.
- **Rubrics:** criteria and maximum scores for assessments.

See [scoring-policy.md](../scoring-policy.md) for the formulas. They are implementation choices, not values from the P06 specification.

## Operations

| Task | Where |
|---|---|
| Health | `/health` (process) and `/ready` (database + cache) |
| Background jobs | **Batch Analytics** (batch readiness) and each drive's **Matching** tab show status, progress, duration and errors. Failed jobs can simply be re-run |
| Audit trail | Django admin → **Audit logs** (read-only) |
| Recruiter access log | **Recruiter Access → Access log** |
| Deploy, back up, restore | [runbooks/](../runbooks/) |
