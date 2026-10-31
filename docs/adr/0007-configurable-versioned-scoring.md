# ADR 0007: Configurable, versioned scoring with immutable snapshots

- Status: accepted (2026-10-21)

## Context
P06 names readiness dimensions but no formula. AGENTS.md requires that scoring is configurable, that results are explainable, and that no formula is presented as coming from the specification.

## Decision
- **Evidence rules** cap what each evidence source can establish, with separate caps for verified and unverified evidence.
- **`ScoringConfig`** holds the readiness weights, the unverified-evidence multiplier, windows and the ready threshold. Publishing a change creates a new version.
- **`ReadinessSnapshot`** rows are append-only. Each stores its scores, the config version that produced it, and an explanation of every input.
- Compatibility, gaps and plans follow the documented rules in [scoring-policy.md](../scoring-policy.md).

## Consequences
- Old results stay explainable after a policy change.
- Institutions can tune scoring without code changes.
- Snapshots accumulate over time; that history also feeds the readiness trend and training-effectiveness reports.
