# ADR 0009: Independent layers for recruiter isolation

- Status: accepted (2026-10-21)

## Context
P06 calls recruiter access the highest-risk surface. The spec requires queryset scoping and serializer field restriction as two independent layers, grant expiry checked in the permission path, logging, throttling and no export.

## Decision
The recruiter API is a separate app and namespace with its own authentication class (recruiter-portal tokens only), throttle scope and `Cache-Control: no-store`. Each request:
1. Resolves a **currently valid grant** for the drive. If there is none, it logs a denial and returns 404.
2. Starts from a queryset of students **registered (or shortlisted)** for that drive, before any search or filter.
3. Serializes candidates **field by field** from the grant's allow-list intersected with a fixed `RELEASABLE_FIELDS` set. Filters and facets exist only for released fields.
4. Writes an **append-only access-log** row.

Pages are capped at 10 and there is no export route; a test pins the exact route list.

## Consequences
- A bug in any one layer does not expose data on its own. A 28-test suite covers each layer, plus the cross-drive negative case required by the spec.
- Adding a releasable field requires a code change, a documentation update and tests, deliberately.
