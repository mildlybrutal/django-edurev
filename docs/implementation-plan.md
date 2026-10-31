# P06 Placement Skill Matcher & Readiness Analyser: Architecture & Phased Plan

## Context

The repository is close to empty. The goal is to build the P06 platform: evidence leads to verified skill profiles, those are compared with drive requirements, and the output is **eligibility and readiness kept separate**, plus gaps, a preparation plan, analytics and scoped recruiter access. It uses Django + DRF + PostgreSQL with a Next.js frontend. **Status:** approved 2026-10-20. Update this document as phases complete or decisions change.

Labels used below:
- **[Spec]**: required by the P06 spec or its Common Engineering Standard (CES), from `Project_Description.pdf`, pp. 1–5 and 24–26.
- **[AGENTS]**: required by `AGENTS.md`.
- **[Decision]**: my proposed implementation choice. It is not a requirement and can be changed.

---

## 1. What exists today

| Area | State |
|---|---|
| Git | 1 commit (`first`). Tracked: `.gitignore` and `myproject/` (output of `django-admin startproject`). Untracked: `frontend/`, `AGENTS.md`, `CLAUDE.md`, the PDF, and agent tool dirs (`.claude/`, `.agents/`, `.agent/`, `.codex/`, `.gemini/`, `.impeccable/`, which hold an "impeccable" design-review skill/hooks) |
| Backend | `myproject/myproject/settings.py`: **Django 6.1.1** defaults, SQLite, `DEBUG=True`, **hard-coded `SECRET_KEY` committed to git**, no DRF, no apps, no custom user model, `MAILERS` (a Django 6.x setting). There is no requirements/pyproject file and no venv |
| Frontend | `create-next-app` boilerplate: **Next 16.4.2, React 19.3, Tailwind v4** (via `@tailwindcss/turbopack`), TS strict, ESLint 9. `next.config.ts` turns on `cacheComponents`, `partialPrefetching` and `experimental.agentFeedback`. There is a `package-lock.json` but **no `node_modules`**. `frontend/AGENTS.md` says to read `node_modules/next/dist/docs/` before writing any Next code, because this Next version has breaking changes |
| Infra | No Docker, compose, CI, Celery, Redis, tests, docs or `.env.example`. Host has Python 3.14, Node 22 and Docker. psql and redis-server are not installed, so they'll run in Docker |

## 2. Gaps and conflicts to resolve

**Conflicts with the spec. These need your decision:**
1. **Django version.** CES §1.1 mandates *"Python 3.12, Django 5.x (LTS release), PostgreSQL 16"*. The scaffold uses Django 6.1 on Python 3.14. **Recommendation:** pin Django 5.2 LTS on Python 3.12 inside Docker, and rebuild the scaffold. It has no business code, so nothing is lost.
2. **Delivery path.** Next.js + DRF is CES **Path P3**. The P06 spec suggests P2 (React) is "reasonable". P3 is allowed, but it carries the rule *"the server owns business rules and permissions; if a rule is written in both places, delete one"*. The frontend will never compute eligibility, readiness or authorization.
3. **Committed secret.** The `django-insecure-…` key in git history is dev-only and low-risk, but it must move to env and be treated as burned.

**Missing pieces:**
- Custom `User` model. It **must exist before the first migration**.
- Institution scoping on every domain record. CES §1.2 says *"multi-tenant-ready from day one"*.
- Settings split and env config, PostgreSQL, Redis, Celery + Celery Beat (CES: never cron).
- DRF, drf-spectacular (`/api/v1`, OpenAPI), SimpleJWT, throttling, `/health` and `/ready`, JSON logging.
- Immutable audit log for privileged actions (CES §1.4). This is separate from the recruiter `AccessLog`.
- docker-compose (web, worker, beat, postgres, redis, frontend), GitHub Actions (ruff, pytest-django, `makemigrations --check`, pip-audit, secret scan, frontend lint/typecheck/build).
- Frontend: deps not installed, no design tokens or component library (CES requires these before feature work), no API client, no auth, no route groups.
- Docs required by CES/P06: README, ADRs, ERD, role/permission matrix, **data-release policy** (P06 §17), and a scoring-policy document.

## 3. Repository structure [Decision; app-per-module is Spec]

```
/
├── backend/
│   ├── manage.py
│   ├── requirements/{base,dev}.txt        # pinned
│   ├── config/                            # replaces myproject/
│   │   ├── settings/{base,dev,test,prod}.py
│   │   ├── urls.py                        # /api/v1/... , /health, /ready, /api/v1/schema
│   │   ├── celery.py  asgi.py  wsgi.py
│   ├── apps/
│   │   ├── core/          # Institution, TenantModel base, AuditLog, health, shared permissions/pagination
│   │   ├── accounts/      # User, Department, StudentRecord, FacultyAssignment, auth endpoints
│   │   ├── taxonomy/      # M1
│   │   ├── evidence/      # M2
│   │   ├── verification/  # M3
│   │   ├── profiles/      # M4
│   │   ├── assessments/   # M5
│   │   ├── readiness/     # M6
│   │   ├── drives/        # M7 (incl. JD processing + eligibility)
│   │   ├── matching/      # M8
│   │   ├── planning/      # M9
│   │   ├── recruiter/     # M10a – own URL namespace, permissions, throttles (Spec)
│   │   ├── reporting/     # M10b – analytics + batch jobs
│   │   └── notifications/ # notification service (in-app first)
│   │   # each app: models.py, services.py (writes/business logic), selectors.py (reads),
│   │   #           api/{serializers,views,urls,permissions}.py, tasks.py, admin.py, tests/
│   └── conftest.py
├── frontend/
│   ├── app/
│   │   ├── (auth)/login/
│   │   ├── (student)/dashboard, profile, evidence, drives/[id], assessments, plan, progress
│   │   ├── (placement)/placement/dashboard, drives, drives/new, drives/[id]/{jd,requirements,matching}, students, analytics, reports, skills
│   │   └── (recruiter)/recruiter/dashboard, drives/[id], candidates/[id]
│   ├── components/{ui,charts,domain}/
│   ├── lib/api/{schema.d.ts (generated), client.ts, server.ts}, lib/auth/
│   └── tests/{unit,e2e}/
├── docs/{adr/, data-release-policy.md, scoring-policy.md, permissions-matrix.md, erd.md, env.md}
├── docker-compose.yml   .env.example   .github/workflows/ci.yml
```

CES rule [Spec]: apps call each other only through `services.py`/`selectors.py` functions and never query another app's models directly. Cross-app FKs are allowed. Views stay thin: read the request, call a service, serialize the result.

## 4. Domain model & app boundaries

The spec's entity list [Spec] is in **bold**. Everything else is [Decision]. Every model has `institution` FK, `created_at` and `updated_at`.

| App | Models | Notes |
|---|---|---|
| core | Institution, AuditLog | AuditLog is append-only: actor, action, target, before/after, ts, IP [Spec CES] |
| accounts | User (email login), Department, **Student** (roll no, dept, grad year, CGPA, active backlogs, mentor), FacultyAssignment | Roles are Django Groups [Spec]. Academic fields are entered by the officer or imported, never edited by the student |
| taxonomy | **Skill**, **SkillSynonym**, **SkillCluster**, SkillRelation (child→parent "is-a", e.g. React→Frontend Framework), SkillClosure (precomputed ancestors), ProficiencyLevel (ordinal 0–4), TargetRole + RoleSkill | Closure table makes taxonomy expansion one indexed join. Cycles are rejected. pg_trgm + SearchVector for skill lookup [Spec] |
| evidence | **EvidenceItem** (source_type, title, description, source_url/external_ref, extracted_data JSON, submitted_at, verification_status), EvidenceSkillTag (evidence→skill, claimed level) | source_type: ACADEMIC, PROJECT, CERTIFICATION, ASSESSMENT, MOCK_INTERVIEW, GITHUB, LEETCODE, CODECHEF, CODEFORCES, OTHER |
| verification | **Verification** (evidence, reviewer, decision, comment, ts; immutable) | Status: SELF_REPORTED → PENDING → VERIFIED / REJECTED [AGENTS]. Only `verification.services` changes status |
| profiles | **SkillProfile** (per student), SkillClaim (skill, level, confidence, has_verified_support), ClaimEvidence (provenance link) | Rebuilt from evidence and the EvidenceRule config. Every claim lists its evidence [AGENTS] |
| assessments | Rubric, RubricCriterion, **Assessment** (+ scores), **MockInterview** (+ scores) | History is append-only. Dimensions covered: aptitude, technical, communication |
| readiness | ScoringConfig (versioned weights & policies), EvidenceRule (source_type → weight, max level, verified multiplier), **ReadinessSnapshot** (student, optional drive, 4 dimension scores, explanation JSON, config_version, inputs hash) | Snapshots are immutable. Dimensions: Technical Mastery, Aptitude, Communication, Project Depth [Spec] |
| drives | Company, **Drive** (role, dates, registration window, status), JobDescription (raw text, processing status, extracted draft), **DriveRequirement** (skill, required level, weight, mandatory), **EligibilityRule** (typed: MIN_CGPA, BRANCH_IN, MAX_ACTIVE_BACKLOGS, GRAD_YEAR_IN), EligibilityResult (eligible, per-rule reasons), **Registration** (status incl. shortlisted/selected) | **EligibilityResult lives here and never shares a table or field with readiness or compatibility** [Spec] |
| matching | MatchResult (student, drive, compatibility %, per-requirement breakdown, snapshot ref), **GapAnalysis**, GapItem (skill, current, required, impact, rank, suggested action) | |
| planning | **PreparationPlan**, PlanItem (task, resource, start, due, checkpoint flag, status), LearningResource (skill + level → resource) | |
| recruiter | RecruiterProfile, **RecruiterAccessGrant** (recruiter, drive, allowed_fields, expires_at, status, granted_by), **AccessLog** (recruiter, grant, endpoint, student_id(s), ts, IP) | |
| reporting | BatchJob (status, progress, timings) | Reports are mostly selectors over other apps |
| notifications | Notification (recipient, type, payload, read_at), channel interface | In-app first, console email in dev [AGENTS §24] |

**Scoring semantics.** [Decision] All of this is configurable and documented in `docs/scoring-policy.md`. None of it is presented as part of the spec.
- *Compatibility (per drive)* = Σ(match_i × weight_i) / Σ weight_i × 100, where match_i = min(student_level / required_level, 1). The student level comes from exact, synonym or taxonomy-descendant matches. An unverified claim is multiplied by a configurable factor.
- *Readiness (per student; drive-specific for Technical Mastery)* is four dimension scores, each with an explanation listing its inputs. The weights come from ScoringConfig and are recorded on the snapshot.
- *External activity* cannot raise a claim above a configurable cap (EvidenceRule.max_level) unless it is verified. That means "500 LeetCode = Expert" can't happen [AGENTS].
- *Gap impact* = weight × level deficit, with a boost for mandatory requirements, then ranked.
- *JD processing* is deterministic: a synonym/trigram dictionary match plus regexes for CGPA, backlogs, branch and year. It produces a **draft** that the officer must confirm. It is never described as AI [AGENTS].

## 5. Authentication & authorization

**Authentication** [Spec: SimpleJWT on P2/P3; Decision: cookie transport]
- `POST /api/v1/auth/login|refresh|logout`, `GET /api/v1/auth/me`. The access token is short-lived (~10 min) and the refresh token rotates and is blacklisted on use. **Both are stored in httpOnly, Secure, SameSite=Lax cookies** and are never put in localStorage. A custom DRF authentication class reads the cookie. Unsafe methods need a CSRF double-submit token.
- Brute-force lockout on login: a cache-backed failure counter plus a throttle [Spec CES]. TOTP MFA for admin, placement head and officer roles (django-otp) comes in the hardening phase [Spec CES]. SSO is deferred.
- **Recruiter isolation** [Spec §16]: recruiters get separately named cookies scoped to `Path=/api/v1/recruiter/`. The authentication classes reject recruiter tokens outside the recruiter namespace and non-recruiter tokens inside it. Recruiters have their own throttle scope. In production the recruiter portal is served from its own host so the cookie domain isn't shared. Both settings are documented in an ADR.

**Authorization** [Spec: groups + object-level check, enforced twice]
- Groups: `student`, `faculty`, `placement_officer`, `placement_head`, `recruiter`, `admin`, seeded by a data migration.
- Every viewset has **(1)** a permission class (role and object check) and **(2)** a role-filtered `get_queryset`, for example: a student sees only their own records, faculty see their assigned students, officers see their institution, recruiters see only registered students in an active, unexpired grant's drive. Records outside that scope return **404, not 403**, so their existence doesn't leak.
- Reusable permission classes go in `core/permissions.py`. Recruiter-specific ones go in `recruiter/permissions.py`.
- The frontend hides UI by role only for UX. It is never the authorization layer.

## 6. Frontend ↔ backend communication [Decision]

- **Same origin.** In dev, Next `rewrites` proxy `/api/v1/*` to Django. In prod, Nginx routes `/api` to Gunicorn and everything else to Next. This avoids CORS (no `django-cors-headers`), lets httpOnly cookies just work, and keeps CSRF simple.
- **Server components** call Django through `lib/api/server.ts`, which forwards the incoming cookies. **Client components** use TanStack Query [Spec allows on P3] against same-origin `/api/v1`.
- **Typed contract.** drf-spectacular generates the OpenAPI schema, and `openapi-typescript` + `openapi-fetch` build typed clients. CI regenerates the schema and fails if it drifts.
- **Next 16 caching.** `cacheComponents` is on, so every authenticated or recruiter fetch must be explicitly uncached or dynamic. I'll read the bundled Next docs first, as `frontend/AGENTS.md` requires. Recruiter responses also get `Cache-Control: no-store` from Django.
- Long jobs (JD processing, matching, batch readiness) return `202` + job id. The UI polls `GET /jobs/:id` (Channels/SSE isn't needed).
- Pagination has a hard max page size. Errors use DRF's standard shape.

## 7. Security risks (focus: recruiter → student records)

| Risk | Mitigation |
|---|---|
| IDOR: recruiter changes a student/drive id | Queryset is filtered to `registrations__drive=grant.drive` **before** any lookup. Outside that set returns 404. Negative test [Spec] |
| Expired, revoked or future grant still works | Expiry and status checked in the permission class on **every request** [Spec], with no caching of grant validity. Tests cover expiry mid-session |
| Field leakage, e.g. nested evidence exposing email, phone, URLs, CGPA | Serializer fields = `grant.allowed_fields ∩ RELEASABLE_FIELDS` (allowlist, nothing exposed by default). Nested serializers are filtered the same way. Tests check that unapproved fields are absent |
| Search/facet counts leak non-registered students | Facets and counts are computed only from the scoped queryset. Tests compare counts |
| Bulk export via pagination or scraping | No export endpoint [Spec], small max page size, per-recruiter throttle, AccessLog. Optional anomaly alert later |
| Unlogged access | AccessLog is written inside the view path for list/detail/search, holding IDs only and no PII payloads. Placement head can review it. Tests assert log rows |
| Withdrawn registration or a student not shortlisted | Scope to the registration statuses the grant allows. Withdrawal removes visibility right away |
| Session or throttle bleed between recruiter and internal portals | Separate cookie name/path/host and separate throttle scopes [Spec §16] |
| Next.js caching serving one user's data to another | Authenticated fetches uncached, `no-store` headers. Covered by an E2E check |
| Self-verification / scoring inflation | Students can't write `verification_status`. Only verification services change it. Self-reported evidence is discounted by policy |
| Faculty scope | Faculty verify only their assigned students (queryset + permission) |
| XSS via evidence or JD text | React escaping only, no `dangerouslySetInnerHTML`. Text sanitized at the serializer |
| SSRF via external evidence URLs | Store URLs only. Any later fetch (GitHub API) goes through an allowlisted host client in a Celery task |
| File uploads (JD/evidence) | Paste-first. Upload is added later with MIME + magic-byte checks, size caps, and object storage with pre-signed URLs [Spec CES] |
| PII in logs or errors | Structured logs carry IDs, not names, emails or CGPA [Spec CES] |
| Fake data passed off as real | Seed command creates **clearly marked synthetic** students. Dashboards never contain hard-coded metrics [CLAUDE.md] |

## 8. Phased implementation plan

Each phase is one or more small PRs. Every endpoint gets tests for both success and authorization failure.

**Phase 1: Foundation**
- Work: rebuild the backend as `backend/config` (Django 5.2 LTS, Py 3.12) with split settings via env. PostgreSQL 16, Redis, Celery + Beat, DRF, spectacular, SimpleJWT cookie auth, custom User, Institution, groups migration, AuditLog, `/health` + `/ready`, JSON logging, compose, CI, `.env.example`. Frontend: `npm ci`, design tokens + shadcn/ui base, TanStack Query, API client, login page, role-routed layouts with placeholder pages.
- Tests: login ok/bad/lockout, refresh rotation, logout blacklist, `/me`, role-guarded probe endpoint (403/404), CSRF required on POST, recruiter token rejected on internal namespace, health/ready.
- Accept: `docker compose up` brings up the full stack. CI is green. No secrets in the repo. The OpenAPI schema is served.

**Phase 2: Taxonomy (M1)**
- Work: models, closure maintenance service, merge tool, `/skills/*` search (pg_trgm), admin editor, seed taxonomy for **software development, data, testing** [Spec §13].
- Tests: synonym resolves to canonical skill, closure after add/remove, cycle rejected, merge rewires references, fuzzy search, non-admin writes denied.
- Accept: the three role taxonomies are seeded. React → Frontend Framework expansion is queryable.

**Phase 3: Evidence + Verification (M2, M3)**
- Work: EvidenceItem CRUD for the student's own records, skill tagging, faculty verification queue, immutable Verification records, notification hook. External platforms are captured as structured manual entries (handle, stats); live API sync is deferred.
- Tests: student submits; student can't set status or verify own items; faculty verify/reject only for their own students; other students get 404; rejected items carry a reason.
- Accept: verification status is visible for every evidence item.

**Phase 4: Skill Profile (M4)**
- Work: EvidenceRule config, aggregation service, SkillClaim + provenance, debounced recompute (cache-lock + countdown Celery task), profile UI with an evidence drill-down.
- Tests: profile from ≥4 evidence types; verified vs unverified weighting; external cap; provenance listed; N rapid changes cause 1 recompute.
- Accept: Spec AC #1 (≥4 evidence types, verification visible).

**Phase 5: Assessments & Mock Interviews (M5)**
- Work: rubrics, faculty capture, student history views.
- Tests: score bounds validation, only faculty/officer can record, student reads only their own.
- Accept: rubric history exists per student.

**Phase 6: Readiness (M6)**
- Work: versioned ScoringConfig, 4-dimension engine with explanation, snapshots, `/students/:id/readiness`, radar chart [Spec §8].
- Tests: per-dimension math, recompute after new evidence, snapshot immutability + config_version, same inputs give same output.
- Accept: every score can be explained from its stored inputs.

**Phase 7: Drives, JD & Eligibility (M7)**
- Work: Drive lifecycle, JD paste → Celery extraction → officer review/confirm requirements, typed EligibilityRules, eligibility service with reasons, registration (eligibility enforced server-side), shortlist state.
- Tests: eligible, ineligible, multiple rules, failed-criteria explanations, registration blocked when ineligible, JD extraction finds the expected skills and criteria in fixture JDs, officer-only writes.
- Accept: eligibility is shown on its own, separate from readiness.

**Phase 8: Matching & Gaps (M8)**
- Work: compatibility service, async `/drives/:id/match`, GapAnalysis ranked by impact, drive detail view (eligibility | readiness | gaps as separate panels).
- Tests: exact, synonym, taxonomy-expanded, missing and partial matches; **ineligible student still gets compatibility**, so all four eligibility × readiness states are reachable; gap order and specificity.
- Accept: Spec AC #2 and #3.

**Phase 9: Preparation Planning (M9)**
- Work: LearningResource catalogue, plan generator (gaps by impact → dated items before the drive date), calendar UI, progress updates, checkpoint-due notifications via Beat.
- Tests: plan from gaps, dates inside the window and ordered, owner-only progress updates, checkpoint notification fires.
- Accept: Spec AC #4 (dated checkpoints).

**Phase 10: Analytics & Batch (M10b)**
- Work: chunked Celery batch readiness (group of chunks, bulk queries, `bulk_create`), BatchJob progress, readiness distribution, **skill supply vs demand**, gap frequency, verification coverage, funnel, department comparison, officer dashboard.
- Tests: report math on fixtures, N+1 guards (`assertNumQueries`), job status transitions; a perf run against 5,000 synthetic students.
- Accept: Spec AC #7 (<15 min for 5,000 students, measured and reported) and #8.

**Phase 11: Recruiter Portal (M10a)**
- Work: grants (placement head only), recruiter namespace/auth/throttles, scoped queryset, field-filtered serializers, faceted search, AccessLog + review UI, data-release policy doc.
- Tests (**dedicated suite** [Spec §15]): Recruiter A/Drive A sees registered students; **cannot reach a student registered only in Drive B** (detail, search, facets, nested); expired, revoked and future grants; unauthorized drive; unapproved fields absent; direct API calls without a grant; throttling returns 429; every access writes a log row; no export route exists.
- Accept: Spec AC #5 and #6.

**Phase 12: Hardening & polish**
- Work: notifications completed (low-readiness nudge, shortlist result), MFA for privileged roles, Playwright E2E of the spec journey (evidence → verify → profile → drive → gaps → plan → recruiter views shortlist), axe-core in CI, ZAP baseline, coverage ≥70% on services, and the CES docs set.
- Accept: the AGENTS §37 end-to-end demo runs on a freshly seeded empty DB.

## 9. Dependencies (each with reason)

**Backend:**
- `Django 5.2`: spec LTS.
- `djangorestframework`: the API layer.
- `drf-spectacular`: OpenAPI [Spec].
- `djangorestframework-simplejwt`: auth [Spec].
- `psycopg[binary]`: PostgreSQL driver.
- `celery`, `redis`: background jobs and cache [Spec].
- `django-environ`: env config.
- Dev: `pytest`, `pytest-django`, `factory-boy`, `ruff`, `pip-audit`, `coverage`.
- Later, only when the phase needs it: `django-otp` (MFA), `sentry-sdk`, `django-storages` + `boto3` (uploads).

**Frontend:**
- `@tanstack/react-query`: server state.
- shadcn/ui (Radix primitives): the component library [Spec].
- `recharts`: radar and distribution charts.
- `openapi-typescript` + `openapi-fetch`: the typed API contract.
- Dev: `vitest`, `@testing-library/react`, `@playwright/test`, `@axe-core/playwright`.

## 10. Verification approach (every phase)

- `docker compose run --rm web pytest` (with coverage), `ruff check`, `python manage.py makemigrations --check`, `pip-audit`.
- `npm run lint && npx tsc --noEmit && npm run build`, plus vitest. Playwright E2E from Phase 8 onwards.
- Every phase reports the actual test output. Nothing is claimed to work unless it was run.

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-20 | Django 5.2 LTS on Python 3.12 (CES §1.1), replacing the Django 6.1 scaffold ([ADR 0001](adr/0001-stack-and-delivery-path.md)) |
| 2026-10-20 | `myproject/` replaced by `backend/config/` |
| 2026-10-20 | Agent tool dirs (`.claude/`, `.agents/`, `.codex/`, `.gemini/`, `.impeccable/`) left untouched; commit/ignore still to be decided |
| 2026-10-20 | Cookie-only JWT with portal-bound tokens ([ADR 0002](adr/0002-cookie-jwt-and-portal-separation.md)) |
| 2026-10-20 | Same-origin `/api/v1` proxy; authenticated data fetched client-side, pages are static shells ([ADR 0003](adr/0003-same-origin-api-and-client-side-data.md)) |
| 2026-10-20 | Taxonomy expansion via relation DAG + closure table ([ADR 0004](adr/0004-taxonomy-closure-table.md)) |
| 2026-10-20 | Small in-house UI primitives now; adopt Radix/shadcn when complex widgets are needed ([ADR 0005](adr/0005-in-house-ui-primitives.md)). Deviation from §9, which listed shadcn/ui up front |
| 2026-10-20 | Taxonomy writes restricted to the `admin` role (P06 §6); officers and heads read only |

## Progress

Detailed status and evidence: [status.md](status.md).

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: settings, Postgres, auth (cookie JWT, CSRF, lockout), RBAC, audit, Docker, CI, frontend shell | done |
| 2 | Taxonomy (M1) incl. Manage Skills UI (skills, synonyms, links, merge, roles, clusters) | done |
| 3 | Student records, evidence (M2), verification (M3) | done |
| 4 | Skill profile (M4): evidence rules, claims with provenance, debounced recompute | done |
| 5 | Assessments and mock interviews (M5) | done |
| 6 | Readiness (M6): versioned config, 4 explained dimensions, snapshots, radar | done |
| 7 | Drives, deterministic JD processing, eligibility, registration, shortlist (M7) | done |
| 8 | Matching and ranked gaps (M8) | done |
| 9 | Preparation plans with dated checkpoints and reminders (M9) | done |
| 10 | Batch readiness job (5,000 students measured), analytics, supply vs demand (M10) | done |
| 11 | Recruiter portal: grants, scoped API, field release, throttles, access log, 28-test security suite | done |
| 12 | MFA, notifications, Playwright e2e, axe, docs, runbooks | done locally; CI on GitHub, deployment, ZAP and load test outstanding |

Additional decisions: ADRs 0006 (deterministic JD processing), 0007 (versioned scoring), 0008 (stdlib TOTP) and 0009 (recruiter isolation). Deviation from §9: no shadcn/ui (ADR 0005), and no django-otp (ADR 0008).
