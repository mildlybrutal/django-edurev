# API reference

The authoritative, machine-readable contract is the OpenAPI 3 schema at `GET /api/v1/schema/` (served to anyone in dev and to admins only in production). CI fails if it has any warning, or if the frontend's generated types drift from it. This page is the human overview (99 paths).

**Conventions**
- All endpoints are under `/api/v1/` and end with `/`.
- Authentication uses httpOnly cookies. Internal portal: `pa_access`/`pa_refresh`. Recruiter portal: `rc_access`/`rc_refresh`, scoped to `/api/v1/recruiter/`.
- Unsafe methods need `X-CSRFToken` matching the `csrftoken` cookie (`GET /auth/csrf/` sets it).
- Lists are paginated as `{count, next, previous, results}`, 25 per page, `?page=N`. The recruiter candidate list uses 10 per page with no size override.
- Errors use DRF's shape: `{"detail": …}` or `{"field": [...]}`. Objects outside your scope (institution, mentees, own records, recruiter grant) return **404**, not 403, so their existence is not revealed.
- Proficiency levels: `0 None · 1 Beginner · 2 Intermediate · 3 Advanced · 4 Expert`.
- Roles: S student · F faculty · O placement officer · H placement head · A administrator · R recruiter. See [permissions-matrix.md](permissions-matrix.md).

## Platform

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | Liveness (no dependencies touched) |
| GET | `/ready` | anyone | Database + cache reachable, else 503 |

## Authentication: `/api/v1/auth/`

Student self sign-up: `GET signup-options/` (public; institutions with sign-up open, and their departments) and `POST signup/` (public, CSRF, throttled; creates the student, flags the academic record as self-declared, and signs them in).

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `csrf/` | anyone | Set the CSRF cookie |
| POST | `login/` | anyone | `{email, password}` → profile and cookies, or `{"mfa_required": true}` with a 5-minute challenge cookie. 401 on bad credentials or a recruiter account; 429 when locked out or throttled |
| POST | `mfa/verify/` | challenge holder | `{code}` → completes an MFA login |
| POST | `refresh/` | session | Rotate tokens (old refresh token blacklisted) |
| POST | `logout/` | session | Blacklist refresh token, clear cookies |
| GET | `me/` | signed in | `{id, email, names, roles, institution, mfa: {enabled, setup_required}}` |
| POST | `mfa/setup/` | signed in | New TOTP secret + `otpauth://` URI (not cached) |
| POST | `mfa/confirm/` | signed in | `{code}` → turn MFA on; replaces a restricted session with a full one |
| POST | `mfa/disable/` | signed in | `{code}` → turn MFA off (refused for roles that require it) |

## Taxonomy (M1): `/api/v1/skills/`
Read: all internal roles. Write: A. All writes audited.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `` | List (`?cluster=`) / fuzzy search (`?q=`) / create skill |
| GET/PATCH/DELETE | `{id}/` | Detail (synonyms, parents, children) / update / retire |
| GET | `resolve/?name=` | Exact name-or-synonym lookup |
| POST, DELETE | `{id}/synonyms/`, `{id}/synonyms/{synonym_id}/` | Add / remove synonym |
| POST, DELETE | `{id}/parents/`, `{id}/parents/{parent_id}/` | "Satisfies" links (cycle-checked) |
| POST | `{id}/merge/` | Merge into `{skill_id}` |
| GET/POST, GET/PATCH/DELETE | `clusters/`, `clusters/{id}/` | Clusters |
| GET/POST, GET/PATCH/DELETE | `roles/`, `roles/{id}/` | Target roles |
| POST, DELETE | `roles/{id}/skills/`, `roles/{id}/skills/{skill_id}/` | Role requirements |

## Students: `/api/v1/students/`

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `` | F (mentees), O/H/A (institution) | List; `?q=`, `?department=`, `?graduation_year=` |
| POST | `` | O/H/A | Create a student account + academic record |
| GET | `{id\|me}/` | self, mentor, O/H/A | Student record |
| PATCH | `{id\|me}/` | self (headline, links), O/H/A (academic fields, mentor) | Update |
| GET | `{id\|me}/profile/` | same | **Skill profile**: levelled claims, each with supporting evidence and verification status, plus profile completion |
| GET | `{id\|me}/readiness/` | same | **Readiness**: latest general snapshot with per-dimension explanation, and history |
| GET/POST | `departments/` | all / O/H/A | Departments |
| GET | `faculty/` | O/H/A | Faculty list (for mentor assignment) |
| GET/POST | `me/onboarding/` | student | Whether the first-run profile pop-up should show; POST marks it done |
| GET | `{id\|me}/coding/` | self, mentor, O/H/A | Coding-activity score and per-platform ratings with explanation |
| POST | `me/coding/` | self | Set or unlink `github_username` / `leetcode_username`; queues a sync |
| POST | `me/coding/refresh/` | self | Re-sync (at most every 30 minutes); 202 |
| GET | `{id\|me}/resume/` | self, mentor, O/H/A | Current resume: name, size and a 5-minute signed view link. Staff views are audited |
| POST | `me/resume/` | self | Upload a PDF (multipart `file`, ≤5 MB, magic bytes checked); keeps the last 3 versions |
| DELETE | `me/resume/` | self | Delete every version |

## Evidence (M2): `/api/v1/evidence/` and verification (M3): `/api/v1/verification/`

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `evidence/` | S (own), F (mentees), O/H/A | List; `?student=`, `?status=` |
| POST | `evidence/` | S | Submit `{source_type, title, description, source_url, external_reference, extracted_data, tags:[{skill_id, claimed_level}], request_verification}`. Institutional types are refused |
| GET/PATCH/DELETE | `evidence/{id}/` | owner (edit only self-reported/rejected; verified items are locked) | Detail / edit / delete |
| POST | `evidence/{id}/request-verification/` | owner | Self-reported → pending; notifies the mentor |
| GET | `verification/queue/` | F | Mentees' pending evidence, oldest first |
| POST | `verification/{evidence_id}/decide/` | F (mentor only) | `{decision: verified\|rejected, comment}`; a comment is required to reject; immutable record; student notified |

## Assessments (M5): `/api/v1/assessments/`

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET/POST | `rubrics/` | all / O/H/A | Rubrics with criteria |
| GET | `` | S (own), F (mentees), O/H/A | Assessment history (`?student=`) |
| POST | `` | F (mentees), O/H | Record `{student_id, rubric_id, title, skill_id?, assessed_on, scores:[{criterion_id, score}], notes}` → verified institutional evidence |
| GET/POST | `mock-interviews/` | same | Mock interviews `{technical/communication/problem_solving 0–100, feedback, skill_ratings}` |

## Readiness model (M4/M6 configuration): `/api/v1/readiness/`

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `config/` | F/O/H/A | Active scoring config version |
| POST | `config/` | A | Publish a new version (weights, unverified multiplier, windows, threshold) |
| GET | `evidence-rules/` | F/O/H/A | Max level per evidence type (unverified / verified) |
| PATCH | `evidence-rules/{id}/` | A | Change a rule |

## Drives & eligibility (M7), matching & gaps (M8): `/api/v1/drives/`
Students see non-draft drives only. Management is O/H.

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET/POST | `companies/`, `companies/{id}/` | all / O/H | Companies |
| GET/POST | `` | all / O/H | List (`?status=`) / create draft `{company_id, role_title, target_role_id?, location, compensation, registration_opens_at, registration_closes_at, drive_date}` |
| GET/PATCH/DELETE | `{id}/` | all / O/H / O/H (draft only) | Detail incl. requirements and eligibility rules |
| POST, DELETE | `{id}/requirements/`, `{id}/requirements/{skill_id}/` | O/H | Set / remove a skill requirement |
| POST, DELETE | `{id}/eligibility-rules/`, `{id}/eligibility-rules/{rule_type}/` | O/H | `min_cgpa`, `max_active_backlogs`, `department_in`, `graduation_year_in` |
| POST | `{id}/apply-role/` | O/H | Seed requirements from a target role |
| GET/POST | `{id}/jd/` | O/H | Submit JD text (202; processed on the worker) / read status and extraction |
| POST | `{id}/jd/apply/` | O/H | Apply the officer-reviewed subset of the extraction |
| POST | `{id}/transition/` | O/H | `published` (runs matching + notifies students), `registration_closed`, `shortlisting`, `completed`, `cancelled` |
| POST/GET | `{id}/match/` | O/H | Start the background matching job (202) / list results with eligibility and compatibility side by side (`?eligible=`, `?registered=`, `?min_compatibility=`, `?q=`) |
| GET | `{id}/jobs/` | O/H | Recent matching jobs and progress |
| GET | `{id}/students/{student_id}/` | O/H | One student's full evaluation for the drive |
| GET | `{id}/registrations/` | O/H | Registered students |
| POST | `{id}/registrations/{registration_id}/decide/` | O/H | `shortlisted`, `not_shortlisted`, `selected`, `not_selected` (student notified) |
| GET | `{id}/my-evaluation/` | S | **Separate blocks**: eligibility (reasons), compatibility (per-requirement breakdown), drive readiness (snapshot), ranked gaps, registration, plan id. Recomputed when stale |
| POST | `{id}/register/`, `{id}/withdraw/` | S | Register (eligibility enforced server-side) / withdraw while open |

## Preparation plans (M9): `/api/v1/preparation-plans/`

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `` | S (own), staff (visible students) | Plans with progress (`?student=`, `?status=`) |
| POST | `` | S | `{drive_id}` → generate a dated plan from the current gaps (previous active plan for that drive is archived) |
| GET | `{plan_id}/` | owner / staff | Items (task, resource, start, due, checkpoint, status) |
| PATCH | `items/{item_id}/` | owner | `{status: todo\|in_progress\|done}` |
| GET/POST | `resources/` | all / F/O/H/A | Learning resources per skill and level |

## Reporting (M10): `/api/v1/reports/` and dashboards

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `reports/overview/` | O/H/A | Totals, readiness distribution, recent drives, top gaps |
| GET | `reports/drives/{id}/supply-demand/?population=all\|eligible` | O/H/A | **Skill supply vs drive demand** |
| GET | `reports/demand/` | O/H/A | Demand across active drives vs supply |
| GET | `reports/gaps/?drive=` | O/H/A | Gap frequency |
| GET | `reports/verification-coverage/` | O/H/A | Evidence by status/source, student coverage |
| GET | `reports/drives/{id}/funnel/` | O/H/A | Evaluated → eligible → registered → shortlisted → selected |
| GET | `reports/departments/` | H/A | Department comparison |
| GET | `reports/training-effectiveness/` | H/A | Readiness change vs plan engagement (observational) |
| GET/POST | `reports/batch-readiness/` | O/H/A | Recent jobs / start the batch readiness job (202) |
| GET | `reports/jobs/{job_id}/` | O/H/A | Job status and timing |
| GET | `dashboard/student/` | S | Student dashboard payload |
| GET | `dashboard/faculty/` | F | Faculty dashboard payload |
| GET, POST | `notifications/`, `notifications/unread/`, `notifications/mark-read/` | signed in | Own in-app notifications |

## Recruiter portal (M10): `/api/v1/recruiter/`
Recruiter tokens only (separate cookies and throttle scope). Read-only. **There is no export endpoint.**

| Method | Path | Purpose |
|---|---|---|
| POST | `auth/login/`, `auth/mfa/verify/`, `auth/refresh/`, `auth/logout/` | Recruiter session |
| GET | `me/` | Recruiter account |
| GET | `drives/` | Drives with a currently valid grant (fields released, expiry, candidate count) |
| GET | `drives/{drive_id}/candidates/` | Scoped candidates: `?q=` skill search (taxonomy-expanded), `?department=`, `?min_compatibility=` (each only if that field is released). Includes facets counted from the scoped set only. Logged |
| GET | `drives/{drive_id}/candidates/{student_id}/` | One candidate, released fields only. Logged; denied attempts are logged too |
| GET | `drives/{drive_id}/candidates/{student_id}/resume/` | 5-minute signed link to the candidate's resume, only when the grant releases `resume`. Each request is logged as a `resume` access |

## Recruiter administration: `/api/v1/recruiter-admin/` (H only)

| Method | Path | Purpose |
|---|---|---|
| GET | `fields/` | Releasable fields and their labels |
| GET/POST | `recruiters/` | Recruiter accounts |
| GET/POST | `grants/` | Grants `{recruiter_id, drive_id, allowed_fields, candidate_scope, starts_at?, expires_at}` |
| PATCH/DELETE | `grants/{grant_id}/` | Change fields/expiry/scope / revoke |
| GET | `access-logs/` | Access log (`?recruiter=`, `?drive=`, `?action=`) |
