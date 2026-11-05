# Project status

_Last updated: 2026-11-06_

## Summary

All 12 phases of the [implementation plan](implementation-plan.md) are implemented, and every P06 acceptance criterion has a passing automated test or a measurement behind it. The remaining work is operational: deployment and a few CES items (see [Not done](#not-done)).

## Verified results (2026-10-21, local Docker stack)

| Check | Result |
|---|---|
| Backend `pytest` (PostgreSQL 16) | **271 passed** (2026-11-06), 87% statement coverage at last measurement (2026-10-21) |
| `ruff check` / `ruff format --check` / `makemigrations --check` | clean |
| OpenAPI `spectacular --validate --fail-on-warn` | 0 warnings, 0 errors (99 paths) |
| `pip-audit` / `npm audit --omit=dev` | no known vulnerabilities. Full `npm audit` reports 8 advisories in **dev-only** tooling (vitest's `tinypool`, `eslint-config-next`'s glob deps); fixes need a vitest 3→5 major upgrade, not yet done |
| Frontend `prettier --check`, `eslint`, `tsc` | clean |
| Frontend unit and component tests (vitest) | **31 passed** (2026-11-06) |
| `next build` | succeeds |
| Playwright end-to-end journey (P06 §15) | **passed**: evidence → verified → profile updates → JD-driven drive published → eligibility, readiness and gaps → plan → shortlist → recruiter grant → recruiter sees the shortlist, an unauthorized drive returns not found, and access is logged |
| Playwright self sign-up → onboarding pop-up → resume upload and view | **passed** |
| axe-core on login, sign-up, all student pages (light) and student, sign-up and placement pages (dark) | **0 critical, 0 serious** violations |
| Live checks (dev stack) | GitHub REST and LeetCode GraphQL fetch and rate a public sample account; resume upload to SeaweedFS; a signed link returns the PDF, an unsigned one 403 |
| Batch readiness, 5,000 synthetic students, on the Celery worker | **14.0 s** (24.7 s including an active-drive rematch); target is < 15 min |
| Drive matching, 5,000 students | 9.3 s |

## P06 acceptance criteria

| Criterion | Evidence |
|---|---|
| Skill profile from ≥4 evidence types, verification status visible | `apps/profiles/tests/test_profiles.py::test_profile_assembled_from_four_evidence_types_with_status`; Profile and Evidence screens |
| Eligibility and readiness computed and displayed independently | `apps/matching/tests` (all four eligible/ready combinations); `evaluation.test.tsx`; separate cards in the UI |
| Ranked, specific, actionable gaps for any student against any drive | `test_gaps_are_ranked_specific_and_actionable` |
| Preparation plan with dated checkpoints | `apps/planning/tests`; calendar view; e2e |
| Recruiter cannot access students outside the approved drive (negative tests) | Dedicated 28-test suite `apps/recruiter/tests/test_recruiter_security.py`; e2e |
| All recruiter access logged and reviewable | Access-log tests; Recruiter Access screen |
| Batch readiness for 5,000 students as a background job in < 15 min | `manage.py run_batch_readiness` measurement above |
| Skill supply-against-demand report for a real drive | `test_supply_demand_for_drive`; Supply vs demand tab and Reports page |
| Taxonomy for software development, data and testing roles | `seed_taxonomy` tests |

## What was built

| Area | Contents |
|---|---|
| Platform | Auth (cookie JWT, CSRF, lockout, MFA/TOTP), RBAC with portal separation, audit log, jobs, notifications |
| M1 | Taxonomy |
| M2 | Evidence |
| M3 | Verification |
| M4 | Skill profile, debounced recompute |
| M5 | Assessments and mock interviews |
| M6 | Readiness, versioned scoring |
| M7 | Drives, deterministic JD processing, eligibility, registration and shortlist |
| M8 | Matching and gaps |
| M9 | Planning, checkpoint reminders |
| M10 | Reports, batch job, recruiter portal |
| Frontend | Student, faculty, placement and recruiter portals. "Module Booklets" design system (DESIGN.md): cobalt rail, cluster-coloured numbered module spines, violet next step, light/dark/system theme, toasts, micro-interactions with a reduced-motion path |
| Self sign-up & onboarding | Public student sign-up (per-institution switch, optional email domain; academics self-declared until the cell confirms them); first-run pop-up for GitHub, LeetCode, LinkedIn and resume |
| Coding activity | GitHub (official API) and LeetCode (unofficial GraphQL) sync on Celery, explainable 0–100 ratings, unverified evidence items, fifth readiness dimension (weight 10) |
| Certificates | Certification evidence can carry an uploaded file (PDF/image) in the same private storage, checked for size, extension and magic bytes; viewed through short-lived signed links |
| Excel import/export | Placement cell and faculty can export staff lists to `.xlsx` (formula-injection safe) and bulk-import students from an ERP/SIS sheet, validated all-or-nothing. **No export exists on the recruiter portal** |
| Recruiter broadcasts | A recruiter with an active grant can send an in-app announcement to the candidates inside that grant (all, or shortlisted only), delivered by a Celery task; every broadcast is listed for the placement cell |
| Resumes | PDF upload to S3-compatible storage (SeaweedFS in compose), private bucket, 5-minute signed view links, staff views audited, recruiter release by grant |
| Demo and tooling | Synthetic demo seed; 5,000-student load generator; CI with e2e |

Design choices are documented in [scoring-policy.md](scoring-policy.md), [data-release-policy.md](data-release-policy.md), [permissions-matrix.md](permissions-matrix.md) and [adr/](adr/).

## Not done

| Item | Notes |
|---|---|
| CI on GitHub | Runs on every push and pull request. The first run (2026-10-31) failed on a gitleaks false positive (test fixture passwords) and stale generated API types; both fixed 2026-11-06 |
| Deployment | No staging or production deployment. [Deployment runbook](runbooks/deployment.md) written but not exercised. [Backup/restore](runbooks/backup-restore.md) verified locally only |
| Recorded handover walkthrough | Not recorded (CES §1.6) |
| File uploads | Resumes and certification files upload to S3-compatible storage (size, extension and magic bytes are checked). **No malware scanning.** Other evidence and JDs are still links/pasted text |
| Live external-platform APIs | GitHub and LeetCode are fetched (LeetCode via an unofficial endpoint that may break). CodeChef and Codeforces are still manual evidence. LinkedIn is stored as a link only (no API) |
| SSO, SMS, ERP/LMS integrations | Not implemented (email channel uses Django's mail backend) |
| Field-level encryption, DPDP data-subject endpoints | Not implemented |
| Load test (Locust/k6), OWASP ZAP baseline | Not run (only the batch-job benchmark was measured) |
| Sentry, i18n string externalisation | Not done |
| Audit-log immutability | Enforced in the ORM, not with a database trigger |
| Transitive Python dependencies | Not locked |
