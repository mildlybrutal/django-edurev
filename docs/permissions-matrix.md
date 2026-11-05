# Role and permission matrix

Every rule is enforced on the server **twice**: by a DRF permission class (role) and by a filtered queryset (scope). UI hiding is a convenience only. Objects outside a user's scope return **404**. All data is limited to the user's institution.

Legend: ✅ allowed · ⛔ denied · 🔒 own/scoped only (see note).

| Capability | Student | Faculty | Placement Officer | Placement Head | Administrator | Recruiter |
|---|---|---|---|---|---|---|
| Sign in to the internal portal | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ (recruiter portal only) |
| Two-factor authentication | optional | optional | **required in production** | **required in production** | **required in production** | optional |
| Read skill taxonomy | ✅ | ✅ | ✅ | ✅ | ✅ | ⛔ |
| Edit taxonomy, clusters, target roles | ⛔ | ⛔ | ⛔ | ⛔ | ✅ | ⛔ |
| View student records | 🔒 self | 🔒 mentees | ✅ | ✅ | ✅ | 🔒 grant (released fields) |
| Edit academic record / mentor | ⛔ (own links & headline only) | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Create students / departments | ⛔ | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Self sign-up (public, only where the institution enables it; optional email domain) | ✅ creates own student account | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| Confirm self-declared academics (`academic_record_verified`) | ⛔ | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Link GitHub / LeetCode, refresh ratings | 🔒 self | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| View coding-activity ratings | 🔒 self | 🔒 mentees | ✅ | ✅ | ✅ | 🔒 grant releases `coding_activity` |
| Upload / replace / delete resume | 🔒 self | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| View resume (5-minute signed link; staff and recruiter views logged) | 🔒 self | 🔒 mentees | ✅ | ✅ | ✅ | 🔒 grant releases `resume` |
| Submit / edit / delete evidence | 🔒 own; unverified only | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| Upload / replace certificate file (PDF/PNG/JPEG) on certification evidence | 🔒 own; self-reported or rejected only | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| View certificate file (5-minute signed link; staff views audited) | 🔒 self | 🔒 mentees | ✅ | ✅ | ✅ | ⛔ never released |
| Mentee summaries (academics, readiness, evidence, drives, plan progress) and per-student drive list | 🔒 self (drives) | 🔒 mentees | ✅ | ✅ | ✅ | ⛔ |
| Excel export: students, evidence (filtered; audited) | ⛔ | 🔒 mentees only | ✅ | ✅ | ✅ | ⛔ **no export of any kind** |
| Excel export: drive match results (filtered; audited) | ⛔ | ⛔ | ✅ | ✅ | ⛔ | ⛔ |
| Excel import: students (validate first, all-or-nothing; audited) | ⛔ | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Verify or reject evidence | ⛔ never own | 🔒 mentees | ⛔ | ⛔ | ⛔ | ⛔ |
| Record assessments / mock interviews | ⛔ | 🔒 mentees | ✅ | ✅ | ⛔ | ⛔ |
| Create rubrics | ⛔ | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Change scoring config / evidence rules | ⛔ | ⛔ | ⛔ (read) | ⛔ (read) | ✅ | ⛔ |
| See drives | published+ | published+ | all incl. drafts | all incl. drafts | published+ | 🔒 granted drives |
| Create/edit drives, JD, requirements, eligibility, lifecycle | ⛔ | ⛔ | ✅ | ✅ | ⛔ | ⛔ |
| Register / withdraw for a drive | 🔒 self, if eligible | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ |
| Own drive evaluation (eligibility, match, readiness, gaps) | 🔒 self | ⛔ | ✅ any student | ✅ any student | ⛔ | ⛔ |
| Run matching, shortlist, select | ⛔ | ⛔ | ✅ | ✅ | ⛔ | ⛔ |
| Preparation plans | 🔒 generate & update own | 🔒 read mentees' | read | read | read | ⛔ |
| Batch analytics, supply vs demand, gaps, coverage, funnel | ⛔ | ⛔ | ✅ | ✅ | ✅ | ⛔ |
| Department comparison, training effectiveness | ⛔ | ⛔ | ⛔ | ✅ | ✅ | ⛔ |
| Recruiter accounts, grants, access-log and broadcast review | ⛔ | ⛔ | ⛔ | ✅ | ⛔ | ⛔ |
| Browse candidates | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | 🔒 registered (or shortlisted) students of an active, unexpired grant; released fields only; throttled; logged; no export |
| Broadcast a notification to a drive's candidates | ⛔ | ⛔ | ⛔ | ⛔ | ⛔ | 🔒 candidates of an active, unexpired grant only (all or shortlisted); recipients resolved server-side, never listed back; 5 per drive per 24 h; logged |
| Notifications | 🔒 own | 🔒 own | 🔒 own | 🔒 own | 🔒 own | ⛔ |
| Django admin | superuser / staff only, independent of roles | | | | | |

Where each rule is tested:

| Rules | Tests |
|---|---|
| Authentication, portals, MFA | `apps/accounts/tests/` |
| Taxonomy | `apps/taxonomy/tests/test_api.py` |
| Student scope | `apps/students/tests/` |
| Evidence and verification (incl. certificate files) | `apps/evidence/tests/`, `apps/verification/tests/` |
| Excel export/import, mentee summaries | `apps/reporting/tests/test_excel.py` |
| Recruiter broadcasts | `apps/recruiter/tests/test_broadcasts.py` |
| Assessments | `apps/assessments/tests/` |
| Drives | `apps/drives/tests/` |
| Reports | `apps/reporting/tests/` |
| Recruiter isolation (dedicated suite, 28 tests) | `apps/recruiter/tests/test_recruiter_security.py` |
