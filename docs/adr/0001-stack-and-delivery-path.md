# ADR 0001: Django 5.2 LTS on Python 3.12, delivered on CES Path P3 (DRF + Next.js)

- Status: accepted (2026-10-20)

## Context
The initial scaffold used Django 6.1 on Python 3.14. CES §1.1 mandates Python 3.12, a Django 5.x LTS release and PostgreSQL 16. The project brief asks for a Next.js + TypeScript + Tailwind frontend. P06 itself suggests Path P2 (React + DRF) because the student dashboard is interactive.

## Decision
Use Django 5.2 LTS on Python 3.12 (in Docker) and PostgreSQL 16. Replace the scaffold (it had no business code) with `backend/config`. Deliver on **Path P3**: DRF serves `/api/v1`, and Next.js (App Router) is the frontend.

## Consequences
- Matches the mandated stack. LTS support covers the project's lifetime.
- Path P3 carries the CES rule that business logic and authorization live only on the server. The frontend never re-implements them.
- Two frameworks to run locally; docker-compose starts both.
