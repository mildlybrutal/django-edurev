# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Students** (primary). Final- and pre-final-year students preparing for campus placement drives. Their job: understand "Am I ready for this specific role, and what do I need to improve?", build an evidence-backed profile, and follow a preparation plan. They **sign up themselves**, then complete their profile (GitHub, LinkedIn, LeetCode links, resume) right after sign-up.
- **Faculty mentors.** They verify their mentees' evidence and record assessments and mock interviews.
- **Placement officers and the placement head.** They run drives (company JD → requirements → eligibility → publish → matching → shortlist), read batch analytics, and (head) control recruiter access.
- **Administrators.** They configure the skill taxonomy, evidence rules and scoring.
- **Recruiters** (restricted). They see only students registered for an approved drive, only released fields, time-boxed and logged.

## Product Purpose

An institutional placement-readiness platform. It converts fragmented student evidence into verified skill profiles, evaluates students against specific placement roles, identifies ranked skill gaps, and generates dated preparation plans. It gives the placement cell batch-level readiness analytics and gives recruiters controlled access to approved candidates. Success: gaps are found weeks before a drive, training is targeted, and the batch readiness picture is defensible.

## Positioning

Moves placement preparation from "Am I eligible?" (CGPA, branch, backlogs) to "Am I ready for this specific role, and what do I need to improve?". **Eligibility and readiness are always separate computations and are never merged in data or UI.** Readiness is explainable, with every score traceable to evidence, assessments and requirements.

## Operating Context

- An institutional web app used daily during placement season by the placement cell and faculty, and repeatedly by students around drives.
- Workflows: evidence → verification → skill profile → drive requirements (from a pasted JD, mapped to the institutional skill taxonomy) → matching → eligibility + readiness → gaps → preparation plan → registration → shortlist → recruiter access.
- Indian university context: CGPA, departments (CSE, IT, ECE, …), batches by graduation year, DPDP Act alignment.

## Capabilities and Constraints

- Backend Django + DRF + PostgreSQL, Celery + Redis. Frontend Next.js + TypeScript + Tailwind CSS. Modular monolith.
- Evidence sources: academic, projects, certifications, assessments, mock interviews, GitHub, LeetCode, CodeChef, Codeforces, **resume (PDF)**.
- **Coding activity** (GitHub via its official API; LeetCode via its unofficial public GraphQL endpoint, labelled as an unofficial source) produces an explainable rating per platform. It counts as a **separate, configurable readiness dimension** and is always labelled unverified external evidence. Activity alone is never treated as proof of expertise.
- **Resumes** are core evidence. Every student is expected to upload one. Staff can view it, and recruiters only if the field is released. Files are stored in S3-compatible object storage and served via short-lived pre-signed URLs.
- Recruiter access: drive-scoped, field-level, time-bounded, rate-limited, fully logged, no bulk export.
- Formulas and weights are implementation choices (documented in `docs/scoring-policy.md`), never presented as part of the P06 specification. No AI is used, and the product must not claim it.

## Evidence on Hand

- All demo data is **synthetic** (`seed_demo`). There are no real students, testimonials, customers or metrics. Mock or demo numbers must stay clearly distinguishable from real data and must never be fabricated in UI copy.

## Product Principles

1. Eligibility and readiness are independent; show both, never blend them.
2. Explain every score: show why a skill, level or readiness value exists.
3. Verification is visible everywhere; unverified evidence is labelled and counts for less.
4. Recruiter data never leaves its approved drive and released fields.
5. Actionable over decorative: every gap comes with a concrete next step.

## Accessibility & Inclusion

WCAG 2.2 AA for all student-facing screens (CES §1.3); zero critical axe violations enforced in end-to-end tests. Responsive down to 360 px. Status is never conveyed by colour alone.
