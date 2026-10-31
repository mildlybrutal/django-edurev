# ADR 0006: Deterministic, officer-reviewed JD processing

- Status: accepted (2026-10-21)

## Context
P06 requires that a pasted JD becomes structured requirements mapped to the institutional taxonomy. AGENTS.md says the JD layer may be deterministic and forbids calling the system AI-powered unless AI is implemented.

## Decision
JD processing (`apps/drives/jd.py`) runs on the Celery worker and matches the text against the institution's skill names and synonyms:
- **Skill matching:** word-boundary aware, longest term first.
- **Level and mandatory status:** inferred from wording in the same sentence ("strong", "familiar", "must", "good to have").
- **Eligibility:** regular expressions extract CGPA, backlog, department and batch criteria.

The output is a **draft** that the officer reviews, edits and applies. Nothing is applied automatically.

## Consequences
- Results are predictable, explainable (each skill shows the sentence it came from) and testable.
- Skills missing from the taxonomy are not found; the fix is to extend the taxonomy.
- A learned extractor could later sit behind the same review step.
