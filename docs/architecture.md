# Architecture

## Overview

```
Browser ─► Next.js (frontend/) ─rewrite /api/v1/* ─► Django + DRF (backend/) ─► PostgreSQL 16
            static shells +                              │
            client components                            └─► Redis ◄─► Celery worker + Celery Beat
```

- **Modular monolith** (CES §1.2, AGENTS §13): one Django app per functional module, no microservices.
- **The server owns all business rules and authorization** (CES Path P3). The frontend renders API data and never computes eligibility, readiness or permissions.

## Backend apps

| App | Module | Responsibility |
|---|---|---|
| `core` | platform | `Institution`, `TenantModel`, append-only `AuditLog`, `BackgroundJob` + `execute_job`, health checks, JSON logging, shared API helpers |
| `accounts` | platform | Email-login `User`, roles (groups), cookie-JWT auth with portal-bound tokens, lockout, TOTP MFA (`totp.py`), permission classes |
| `taxonomy` | M1 | Skills, synonyms, "satisfies" relations + closure table, clusters, target roles; fuzzy search; starter seed |
| `students` | M2 support | Department, `StudentProfile` (academic record, mentor); visibility selectors |
| `evidence` | M2 | `EvidenceItem` (source, provenance, status), skill tags; `evidence_changed` signal |
| `verification` | M3 | Immutable `Verification` decisions; mentor-only rules |
| `profiles` | M4 | `EvidenceRule` caps, `SkillClaim` + `ClaimEvidence` provenance, debounced recompute task |
| `assessments` | M5 | Rubrics, assessments, mock interviews; each becomes verified institutional evidence |
| `readiness` | M6 | Versioned `ScoringConfig`, immutable `ReadinessSnapshot`, scoring policy |
| `drives` | M7 | Companies, drives + lifecycle, requirements, typed eligibility rules + results, registrations, deterministic JD processing |
| `matching` | M8 | Compatibility scoring, `MatchResult`, ranked `GapItem`s, drive matching job |
| `planning` | M9 | Learning resources, plan generator, plan items, checkpoint reminders |
| `reporting` | M10 | Analytics services, batch-readiness job, dashboards |
| `recruiter` | M10 | Grants, append-only `AccessLog`, recruiter API with its own auth/throttles, field-filtered serializer |
| `notifications` | cross-cutting | In-app notifications with a pluggable channel list (email channel included) |
| `demo` | tooling | Synthetic demo seed, 5,000-student load generator, batch benchmark command |

### Layering rules

- `models.py` holds data and constraints.
- `services.py` holds writes and rules, and is unit-testable without HTTP. `selectors.py` holds reads.
- `api/` holds serializers and views. Views stay thin.
- Apps use each other's services/selectors and signals (`evidence_changed`, `skill_merged`). Cross-app foreign keys are allowed.

## Core data flow

```
evidence (+ verification) ──► skill claims (capped by evidence rules, verified level kept separately)
                                   │
assessments / mock interviews ─────┤──► general readiness snapshot (4 dimensions + explanation)
                                   │
drive requirements + taxonomy ─────┴──► per drive: eligibility result │ compatibility + breakdown │
                                         drive readiness snapshot │ ranked gaps ──► preparation plan
```

- **Eligibility** (`drives/eligibility.py`) reads only the academic record. It is stored in its own table and never combined with skill scores.
- **Recompute triggers:**
  - Evidence changed: a debounced Celery task rebuilds the student's claims and readiness, then rematches that student against every active drive.
  - Drive published, or "Run matching": a drive matching job over every student, chunked.
  - Batch readiness job: all students' claims and readiness, then every active drive.
- Formulas: [scoring-policy.md](scoring-policy.md).

## Authentication and authorization

- **Tokens:** SimpleJWT access and refresh tokens live in httpOnly cookies, never in JavaScript. Refresh tokens rotate and the old one is blacklisted. Unsafe requests require CSRF.
- **Portals:** each token carries a `portal` claim, and internal and recruiter tokens are not interchangeable. Recruiter cookies are scoped to `/api/v1/recruiter/`.
- **Lockout:** per-email lockout, plus per-IP login throttles.
- **MFA:** RFC 6238 TOTP. Password-verified users with MFA get a signed 5-minute challenge instead of tokens. Roles in `MFA_REQUIRED_ROLES` get a restricted session that can only reach `/auth/*` until they enrol.
- **Authorization:** each endpoint applies a role permission class *and* a scoped queryset (institution, own record, mentees, or recruiter grant). Records outside that scope return 404.
- **Recruiter portal**, five independent controls checked on every request:
  1. a valid grant (active, started, unexpired);
  2. a queryset limited to registered (or shortlisted) students of that drive;
  3. a serializer that only emits released fields;
  4. its own throttle scope;
  5. an access-log row per request, including denials.

  There is no export endpoint. See [data-release-policy.md](data-release-policy.md).
- **Audit:** `record_audit` covers logins, taxonomy edits, verification decisions, assessments, drive changes, registration decisions, grants and configuration changes.

## Frontend

- **Next.js 16 App Router** with `cacheComponents`. Pages are static shells, and authenticated data is fetched in client components with TanStack Query, so user data never enters Next's server cache. Portal layouts stream behind `<Suspense>`.
- **Same-origin API.** `/api/v1/:path*` is rewritten to Django, adding back the trailing slash. A typed client is generated from OpenAPI (`lib/api/schema.d.ts`), and `lib/api/http.ts` adds CSRF and one portal-aware refresh-and-retry. Computed report payloads are typed in `lib/api/types.ts`.
- **Route trees:**
  - `/student/*`, `/faculty/*`, `/placement/*` and `/account`: internal portal, via `PortalShell`.
  - `/recruiter/login` and `/recruiter/*`: separate shell and session.
  - `proxy.ts` does an optimistic sign-in redirect only.
- **Design system:**
  - Semantic tokens in `app/globals.css` (light and dark).
  - Primitives in `components/ui/`.
  - Charts in `components/charts/` (radar, line, bars, columns, calendar). They are single-series, use the dataviz reference blue, show values as text, provide hover/focus tooltips, and mark status with an icon plus a label.

## Background processing

Celery workers on Redis run:
- JD processing
- debounced profile recompute
- drive matching
- batch readiness

Celery Beat runs the daily checkpoint reminders. Progress and timing are recorded in `BackgroundJob`, and the UI polls it.

## Deployment shape

- **Images and processes:** the backend image runs Gunicorn as a non-root user. Worker and beat use the same image. The frontend runs with `next build && next start` behind a reverse proxy that routes `/api/` to Django.
- **Production settings:** HTTPS redirect, HSTS, secure cookies, JSON-only rendering, and an admin-only schema.
- **Not yet deployed:** see [status.md](status.md).
