# Placement Skill Matcher & Readiness Analyser

An evidence-based placement readiness platform (EduRev project P06, Track P, Path P3). It turns student evidence into verified skill profiles, evaluates **eligibility and readiness as separate computations** for each placement drive, ranks skill gaps, generates dated preparation plans, gives the placement cell batch analytics, and gives recruiters scoped, logged access to registered candidates.

> **Status (2026-10-21): all 12 planned phases are implemented and tested locally; every P06 acceptance criterion is met.**
> Last verified: 245 backend tests and 28 frontend tests pass (2026-10-31); 87% backend coverage, Playwright end-to-end tests (full journey and sign-up/onboarding) and axe accessibility checks in both themes passed on 2026-10-21. Batch readiness for 5,000 students runs in about 14–25 s on the worker (target < 15 min).
> **Not yet done:** CI on GitHub, deployment, upload malware scanning, CodeChef/Codeforces sync, SSO and some CES operational items. See [`docs/status.md`](docs/status.md).

## The problem

Most placement cells answer one question about a student: **"Are they eligible?"** CGPA, branch, backlogs and graduation year decide who may register for a drive. That check says nothing about whether the student can actually do the job. Students who clear the cut-off often get rejected in technical rounds, and the cell only learns this after the drive.

Several things make this hard to fix today:

- **Evidence is scattered.** Projects sit on GitHub, problem-solving on LeetCode or Codeforces, certificates in PDFs, marks in the ERP, mock-interview feedback in someone's notes. Nobody sees all of it together.
- **Claims are unverified.** A resume line like "Docker, Kubernetes" counts the same as a project a faculty mentor has reviewed.
- **Preparation is generic.** Everyone gets the same aptitude and coding sessions, whatever the upcoming drive needs and whatever each student is missing.
- **The cell can't see the batch.** Before a drive, there is no quick way to see how many students really have the required skills, or which gap is the most common.
- **Recruiter access is loose.** Student data is often shared as spreadsheets, with no limit on who sees what, or for how long.

## How this project solves it

It treats **eligibility** and **readiness** as two separate results, and builds readiness from evidence instead of self-declared skills.

| Problem | What the platform does |
|---|---|
| Eligibility is the only check | Computes eligibility (hard rules, with the reason for each failure) and role-specific readiness as **two independent results**. A student can be *Eligible + Not Ready* or *Not Eligible + Strong Match*, and both are shown. |
| Scattered evidence | Students add academic records, projects, certifications, assessments, mock interviews and GitHub/LeetCode activity as evidence items, each with its source and status. |
| Unverified claims | Faculty mentors verify or reject evidence. Students can't verify their own. Verified and unverified evidence are weighted differently, and the status stays visible from evidence to skill to readiness. External activity counts as supporting evidence, not proof of expertise. |
| Inconsistent skill names | An institutional skill taxonomy with synonyms and relations ("Postgres" = PostgreSQL, React counts toward "frontend framework"), so matching uses one vocabulary instead of loose string matching. |
| Reading JDs by hand | The placement officer pastes a company JD. A rule-based parser (not AI) suggests required skills, levels and eligibility rules, and the officer reviews them before they apply. |
| Opaque or missing readiness | Readiness is broken into Technical Mastery, Aptitude, Communication and Project Depth, with the evidence behind each. Compatibility with a drive is a configurable, documented formula ([`docs/scoring-policy.md`](docs/scoring-policy.md)). It is an implementation choice, not a formula from the P06 specification. |
| Generic preparation | Ranked, specific gaps (current level, required level, impact, suggested action), turned into a preparation plan with resources, dated checkpoints and progress tracking. |
| No batch visibility | Batch readiness distribution, skill supply vs. drive demand, common gaps, verification coverage and drive funnels. Batch readiness for 5,000 students runs as a Celery background job. |
| Loose recruiter access | Recruiters get time-limited grants for a single drive. They see only students registered for that drive, and only the fields the grant allows. Access is rate-limited and logged, there is no bulk export, and negative tests prove the scoping. |

Students are identified by their **8-digit university registration number** (e.g. `12302221`). The API rejects any other format.

## Documentation

| Document | Contents |
|---|---|
| [`docs/status.md`](docs/status.md) | What is done, measured results, acceptance-criteria evidence, what is not done |
| [`docs/architecture.md`](docs/architecture.md) | Apps, data flow, auth and authorization, frontend, background jobs |
| [`docs/erd.md`](docs/erd.md) | Data model diagram and database guarantees |
| [`docs/api.md`](docs/api.md) | All 99 API paths (authoritative schema: `/api/v1/schema/`) |
| [`docs/permissions-matrix.md`](docs/permissions-matrix.md) | Who can do what, and where it is tested |
| [`docs/scoring-policy.md`](docs/scoring-policy.md) | Evidence caps, compatibility, readiness, gaps, plans: all implementation choices |
| [`docs/data-release-policy.md`](docs/data-release-policy.md) | Exactly what recruiters can see (P06 §17) |
| [`docs/env.md`](docs/env.md) | Every environment variable |
| [`docs/guides/`](docs/guides/) | End-user quick-start and administrator guide |
| [`docs/runbooks/`](docs/runbooks/) | Deployment/rollback, backup/restore |
| [`docs/adr/`](docs/adr/) | Architecture decision records |
| [`docs/implementation-plan.md`](docs/implementation-plan.md) | Original plan, decisions log, progress |
| [`DESIGN.md`](DESIGN.md) | Visual design system (Module Booklets): tokens, components, motion |
| [`AGENTS.md`](AGENTS.md) | Product rules for contributors and coding agents |

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework, drf-spectacular (OpenAPI) |
| Auth | SimpleJWT in httpOnly cookies, CSRF, login lockout, TOTP MFA, separate recruiter-portal session |
| Database | PostgreSQL 16 (`pg_trgm` fuzzy skill search) |
| Background jobs | Celery + Celery Beat on Redis 7 |
| Frontend | Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS 4, TanStack Query, typed client generated from OpenAPI |
| Tests | pytest-django, vitest + Testing Library, Playwright + axe-core |
| CI | GitHub Actions: lint/format, tests, migration and schema checks, audits, gitleaks, full-stack e2e |

## Running it

**Prerequisites:** Docker with Compose v2. Node.js 22+ only if you run the frontend or e2e tests on the host.

```bash
cp .env.example .env
# edit .env: set DJANGO_SECRET_KEY (long random), POSTGRES_PASSWORD (also inside DATABASE_URL)
# and RESUME_S3_ACCESS_KEY / RESUME_S3_SECRET_KEY (any random strings)
docker compose up --build
```

This starts seven services:

| Service | Address |
|---|---|
| `frontend` | http://localhost:3000 (Next.js dev; proxies `/api/v1/*`) |
| `backend` | http://localhost:8000 (migrates on start) |
| `worker`, `beat` | Celery |
| `db` | localhost:5432 |
| `redis` | localhost:6379 |
| `objectstore` | localhost:8333 (SeaweedFS S3 gateway for resumes; set `RESUME_S3_ACCESS_KEY`/`RESUME_S3_SECRET_KEY` in `.env`) |

The first build downloads dependencies and can take several minutes.

### Load the synthetic demo

```bash
docker compose exec backend python manage.py seed_demo --password 'Choose-A-Demo-Password'
```

This creates the *Demo Institute (synthetic data)*. Students, evidence, scores, JD text and pay are fictional. The drives use real campus-recruiter names (Capgemini, Accenture, Infosys, TCS) only as labels; the JDs are samples written for the demo, not real postings from those companies.
- a 40-student mentored cohort (registration numbers `12300001`–`12300040`) with projects, certifications, coding profiles, assessments and mock interviews, with mixed verification
- four drives at different stages: Capgemini Backend Engineer (published, from a processed JD), Accenture Data Analyst (published, from a role template), Infosys QA Engineer (in shortlisting) and TCS SDE Intern (draft)
- matching results and a preparation plan
- a recruiter grant

It is idempotent: if the cohort already exists it changes nothing, so run `docker compose down -v` first to pick up changes to the demo data. **Never run it against a database with real student data.**

| Role | Sign in at | Email |
|---|---|---|
| Student | `/login` | `student@demo.example.test` |
| Faculty (mentor) | `/login` | `faculty@demo.example.test` |
| Placement officer | `/login` | `placement.officer@demo.example.test` |
| Placement head | `/login` | `placement.head@demo.example.test` |
| Administrator | `/login` | `admin@demo.example.test` |
| Recruiter | `/recruiter/login` | `recruiter@demo.example.test` |

Students can also **create an account at `/signup`** (enabled for the demo institute). After signing up, a pop-up asks for GitHub, LeetCode, LinkedIn and a resume. The theme switch (light, system, dark) is in the header.

What to try is in [`docs/guides/user-guide.md`](docs/guides/user-guide.md).

### Other addresses

- API schema: http://localhost:8000/api/v1/schema/
- Health: `/health` (liveness) and `/ready` (database + cache)
- Django admin: http://localhost:8000/admin/ (`docker compose exec backend python manage.py createsuperuser`)

### Frontend on the host (faster reload)

```bash
docker compose up -d db redis backend worker beat
cd frontend && npm ci && npm run dev
```

### Stop and reset

```bash
docker compose down        # stop, keep data
docker compose down -v     # also delete the database and node_modules volumes
```

## Tests and checks

**Backend** (in the container, against PostgreSQL):

```bash
docker compose run --rm backend pytest                                            # 245 tests
docker compose run --rm -e COVERAGE_FILE=/tmp/.coverage backend pytest --cov      # 87%
docker compose run --rm backend ruff check .
docker compose run --rm backend ruff format --check .
docker compose run --rm backend python manage.py makemigrations --check --dry-run
docker compose run --rm backend python manage.py spectacular --validate --fail-on-warn --file /tmp/openapi.yml
docker compose run --rm backend pip-audit --cache-dir /tmp/pip-audit -r requirements/base.txt
```

**Frontend:**

```bash
cd frontend
npm run format:check && npm run lint && npm run typecheck && npm test && npm run build
npm run gen:api         # regenerate lib/api/schema.d.ts from the running backend
```

**End-to-end and accessibility** (Playwright, against the running, seeded stack):

```bash
cd frontend && npx playwright install chromium
E2E_PASSWORD='Choose-A-Demo-Password' npm run e2e
```

The journey signs in five times. For repeated local runs add `THROTTLE_LOGIN=60/min` to `.env` and restart the backend. The production default stays 10/min.

**Load test** (the batch-readiness acceptance criterion):

```bash
docker compose exec backend python manage.py seed_synthetic_cohort --institution loadtest --students 5000
docker compose exec backend python manage.py run_batch_readiness --institution loadtest
```

> Writing files from the backend container (e.g. `makemigrations`)? Add `--user "$(id -u):$(id -g)"`.

## Management commands

| Command | Purpose |
|---|---|
| `seed_demo [--password X] [--students N]` | Synthetic demo (see above) |
| `seed_taxonomy <institution_code>` | Starter taxonomy (software development, data, testing roles); never overwrites edits |
| `seed_synthetic_cohort --institution CODE --students N` | Bulk synthetic students for load testing |
| `run_batch_readiness --institution CODE` | Queue the batch job on the worker and report its duration |
| `createsuperuser` | Platform admin for Django admin |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose build` slow on pip | Some networks have broken IPv6 to PyPI. The Dockerfile prefers IPv4, and rebuilds use a pip cache mount |
| `CSRF failed: Origin checking failed` | Add the frontend origin to `CSRF_TRUSTED_ORIGINS` (dev already trusts `http://localhost:3000`) |
| "Request was throttled" on login | Wait a minute, or raise `THROTTLE_LOGIN` locally |
| Styles look stale in the compose frontend | `docker compose restart frontend`. File-watch events don't always cross bind mounts |
| Results look stale after evidence changes | Profile/readiness recompute is debounced (5 s dev, 30 s prod) and runs on the worker. Check `docker compose logs worker` |
| Frontend type errors after API changes | `npm run gen:api` with the backend running |

## Repository layout

```
backend/
  config/            settings (base/dev/test/prod), urls, celery
  apps/core          institution, audit log, background jobs, health
  apps/accounts      users, roles, cookie-JWT, MFA
  apps/taxonomy      M1 skills, synonyms, relations, roles
  apps/students      academic records, departments, mentors
  apps/evidence      M2 evidence
  apps/verification  M3 faculty verification
  apps/profiles      M4 skill claims + evidence rules
  apps/assessments   M5 rubrics, assessments, mock interviews
  apps/readiness     M6 scoring config + snapshots
  apps/drives        M7 drives, JD processing, eligibility, registration
  apps/matching      M8 compatibility + gaps
  apps/planning      M9 preparation plans
  apps/reporting     M10 analytics, dashboards, batch job
  apps/recruiter     M10 recruiter portal + grants + access log
  apps/notifications in-app (+ email) notifications
  apps/demo          synthetic demo and load data
frontend/
  app/               /login, /account, /student/*, /faculty/*, /placement/*, /recruiter/*
  components/        ui/, charts/, domain/, shell/
  lib/               api/ (generated schema, client, types), auth/, nav
  tests/e2e/         Playwright journey + accessibility
docs/                status, architecture, ERD, API, policies, guides, runbooks, ADRs
.github/workflows/   CI
```
