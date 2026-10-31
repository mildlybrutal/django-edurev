# Data-release policy: what recruiters can see

P06 §17 requires a documented policy stating exactly which student fields a recruiter may see. This is that policy, and it is enforced in code (`apps/recruiter/models.py: RELEASABLE_FIELDS`, `apps/recruiter/api/candidates.py`).

## Who can be seen

A recruiter sees a student **only if all** of these hold, checked on every request:

1. The recruiter has a grant for that drive that is **active**, has **started**, and has **not expired**. Revocation or expiry takes effect on the very next request, mid-session included.
2. The student is **registered** for that drive. If the grant is limited to the shortlist, the student must be **shortlisted or later**. Withdrawn students disappear.
3. Recruiter and drive belong to the same institution.

Anything else returns **404** (not 403), so recruiters cannot probe whether a student or drive exists.

## What can be seen

Only fields in this list can ever be released. The placement head chooses a subset per grant.

| Field key | What is released | Default in new grants |
|---|---|---|
| `name` | Full name | ✓ |
| `email` | Institutional email | |
| `department` | Department code and name | ✓ |
| `graduation_year` | Graduation year | ✓ |
| `cgpa` | CGPA | |
| `compatibility` | Skill-match % for this drive | ✓ |
| `readiness` | Readiness % for this drive and its five dimensions | |
| `skills` | Skill names, levels and whether each is verified | ✓ |
| `evidence` | Evidence **titles, types and verification status only**: no descriptions, links, files or identifiers | |
| `registration_status` | Registration / shortlist status | ✓ |
| `coding_activity` | Coding-activity score and per-platform ratings (GitHub, LeetCode), labelled unverified. No usernames or profile links | |
| `resume` | The candidate's current resume PDF, opened through a 5-minute signed link fetched per request. **Each open is logged** (`resume` action) | |

**Never released:** registration number, phone, address, active backlogs, mentor, evidence descriptions, URLs or external references, GitHub/LeetCode/LinkedIn handles and links, resume history, assessment details, notes, audit data, and any other student's data.

Filters and facets follow the same rule. A recruiter can only filter or facet on a field that has been released (e.g. no department filter unless `department` is released). Facet counts are computed from the scoped candidate set only.

## Volume and logging

- No bulk export endpoint exists (verified by test). Candidate lists return 10 per page and the page size cannot be raised.
- Recruiter requests have their own throttle (default 30/min per recruiter; 5/min for recruiter login).
- Every list, search, profile view and **denied** attempt is written to an append-only access log: recruiter, grant, drive, students returned, fields released, query, IP and time. The placement head reviews it under **Placement → Recruiter Access → Access log**.
- Responses carry `Cache-Control: no-store`.

## Changing this policy

Adding a releasable field means changing `RELEASABLE_FIELDS` and `serialize_candidate` in code, updating this document, and extending `apps/recruiter/tests/test_recruiter_security.py`. It cannot be done through configuration.
