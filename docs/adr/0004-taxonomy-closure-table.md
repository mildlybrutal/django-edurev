# ADR 0004: Taxonomy expansion via an explicit relation graph and closure table

- Status: accepted (2026-10-20)

## Context
P06 §8 requires taxonomy-expanded matching: a student with "React" matches a requirement for "frontend framework". AGENTS.md forbids uncontrolled string matching where a taxonomy relationship exists.

## Decision
- Skills form a DAG of `SkillRelation(child → parent)` edges meaning "child satisfies parent". Abstract categories are ordinary skills with `is_abstract=True`.
- Synonyms are separate rows resolving to one canonical skill. Names and synonyms share one per-institution namespace.
- `SkillClosure` stores all (ancestor, descendant, depth) pairs. It is fully rebuilt per institution on each structural edit, and cycles are rejected before insert.
- Fuzzy lookup (pg_trgm) is for finding skills in the UI and JD processing. Matching itself uses only the canonical graph.

## Consequences
- "Does skill S satisfy requirement R, and how directly?" is one indexed lookup. The depth is available to scoring policies.
- Full rebuilds are O(skills × depth). That's fine for hundreds of skills; revisit if a taxonomy grows into the tens of thousands.
- Merges keep the retired skill (`merged_into`) and emit `skill_merged` so other apps can re-point their references.
