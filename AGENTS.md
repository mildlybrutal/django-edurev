# AGENTS.md — Placement Skill Matcher & Readiness Analyser

## 1. Project Identity

**Project:** Placement Skill Matcher & Readiness Analyser  
**Working title:** Evidence-Based Placement Readiness & Skill-Gap Platform  
**Track:** Track P — Python / Django / DRF / PostgreSQL

This is an institutional placement-readiness platform. Its central purpose is to move placement preparation from simple eligibility checks and generic training toward an evidence-backed, role-specific view of student readiness.

### Core problem

A student can be formally eligible for a placement drive and still be unprepared for the role. The system must therefore treat:

- **Eligibility** — hard placement criteria such as CGPA, branch, backlog rules, etc.
- **Readiness / Compatibility** — evidence-backed fit against the actual role requirements

as **two independent computations**.

Never merge these into one score or UI concept.

---

# 2. Product Vision

The core product flow is:

> **Evidence → Verified Evidence → Skill Profile → Role Requirements → Matching → Eligibility + Readiness → Skill Gaps → Preparation Plan**

The Placement Officer creates a placement drive and uploads/pastes the company's JD. The system processes the JD into structured requirements using the institutional skill taxonomy.

Students build evidence-backed profiles from academics, projects, certifications, assessments, mock interviews, and external developer activity such as GitHub, LeetCode, CodeChef, and Codeforces.

The system compares the company's requirements with each student's skill profile and produces:

- eligibility result
- role-specific readiness / compatibility
- skill gaps
- prioritized preparation recommendations
- placement-office batch analytics

Recruiters receive only controlled access to students registered for their approved drive.

---

# 3. Important Product Boundary

The project is **not a Codolio clone**.

A Codolio-inspired unified developer profile is a feature inside the system.

External activity is supporting evidence, not automatic proof of expertise.

Correct conceptual pipeline:

> Raw activity → curated evidence → verified evidence where applicable → skill assertions → role-specific readiness

Examples:

- GitHub → project / technology evidence
- LeetCode → DSA / problem-solving evidence
- CodeChef / Codeforces → competitive-programming evidence
- Certifications → supporting evidence
- Academic records → academic foundations
- Assessments → measured performance
- Mock interviews → technical / communication evidence
- Projects → project-depth evidence

Never make claims such as:

> "500 LeetCode problems = Expert DSA"

unless an explicit scoring policy is implemented and documented.

---

# 4. Primary Users

## Student

Can:

- manage their own profile
- add/view evidence
- connect/add external evidence
- view verification status
- view skill profile
- view available placement drives
- view eligibility for drives
- view role-specific readiness / compatibility
- view skill gaps
- view preparation plans
- track preparation progress
- view assessments and mock-interview history

Cannot:

- self-verify evidence
- access another student's private data
- modify institutional scoring/taxonomy configuration

---

## Faculty

Can:

- review student evidence for their students
- verify project and skill claims
- record assessment results
- record mock-interview evaluations

Verification must be represented explicitly as verified/unverified rather than silently trusted.

---

## Placement Officer

Can:

- create placement drives
- upload/paste company JDs
- configure roles
- configure eligibility criteria
- inspect student details
- run matching
- view compatibility/readiness results
- shortlist/filter students
- view batch readiness analytics
- inspect common skill gaps
- manage placement registrations

---

## Placement Head

Has Placement Officer capabilities plus:

- recruiter access control
- institutional analytics
- broader batch reporting

---

## Recruiter

Can only:

- access their approved placement drive
- view students registered for that drive
- see fields explicitly approved for release
- use scoped candidate search

Recruiter access must be:

- time-bounded
- drive-scoped
- field-level controlled
- rate-limited
- fully logged

There must be **no bulk export endpoint**.

---

## Administrator

Can configure:

- skill framework
- skill synonyms
- skill clusters
- role mappings
- evidence rules
- scoring configuration

---

# 5. Functional Modules

Implement the project around these ten modules.

## M1 — Skill Taxonomy

Maintain:

- Skill
- Skill levels
- Skill synonyms
- Skill clusters
- Role mappings
- equivalences / taxonomy expansion

Example:

```text
Postgres
  └── PostgreSQL
  └── SQL Database

Frontend Framework
  └── React
  └── Next.js
  └── Vue
```

Taxonomy expansion allows a student with "React" to match a requirement such as "frontend framework" where the taxonomy says the relationship is valid.

Do not use uncontrolled string matching when a taxonomy relationship exists.

---

## M2 — Evidence Ingestion

Support evidence from:

- academic records
- projects
- GitHub
- certifications
- assessments
- external coding platforms
- other approved evidence sources

Each evidence item should have provenance and status.

Example:

```text
EvidenceItem
- student
- source_type
- title
- description
- source_url / external_reference
- extracted_data
- submitted_at
- verification_status
```

---

## M3 — Evidence Verification

Faculty verification workflow.

Evidence should distinguish:

```text
SELF_REPORTED
VERIFIED
REJECTED
PENDING
```

The exact enum can be adapted to the codebase, but verification state must be explicit.

The student cannot verify their own evidence.

---

## M4 — Student Skill Profile

Aggregate evidence into a live skill profile.

The profile should expose levelled skill claims such as:

```text
Python       → Intermediate
Django       → Intermediate
PostgreSQL   → Intermediate
Docker       → Beginner
DSA          → Intermediate
```

The UI should also make the supporting evidence discoverable.

Do not hide why a skill exists.

---

## M5 — Assessment & Mock Interview

Capture rubric-driven:

- technical performance
- aptitude
- communication
- mock interview results

Keep assessment history.

---

## M6 — Readiness Engine

Readiness is multidimensional.

Required dimensions from the project specification:

- Technical Mastery
- Aptitude
- Communication
- Project Depth

The engine must provide an explanation of readiness rather than producing an opaque number only.

Important:

**The original project specification does not define an exact percentage formula.**

If implementing a percentage, treat the formula and weights as an implementation decision/configuration, not as an existing requirement from the source document.

---

## M7 — Drive & Eligibility Management

A drive contains:

- company
- role
- JD
- requirements
- eligibility rules
- registration window
- drive dates
- registration state
- shortlist state

The Placement Officer owns this workflow.

---

## M8 — Match & Gap Analysis

Compare:

```text
Company / Role Requirements
            ↓
Skill Taxonomy
            ↓
Student Skill Profile
            ↓
Matching
            ↓
Compatibility / Readiness
            ↓
Skill Gaps
```

Matching must support taxonomy-expanded relationships.

Example:

```text
JD requirement: Frontend Framework
Student skill: React

Taxonomy:
React → Frontend Framework

Result:
Match
```

---

## M9 — Preparation Planning

Convert gaps into an actionable, time-bound plan.

The UI should support:

- prioritized gaps
- resources
- milestones
- checkpoints
- dates
- progress tracking

The source explicitly expects a preparation plan with dated checkpoints.

---

## M10 — Recruiter Portal & Batch Reporting

Two responsibilities:

### Recruiter portal

Scoped candidate search and controlled student information release.

### Placement analytics

Examples:

- batch readiness distribution
- skill supply vs drive demand
- common skill gaps
- verification coverage
- drive funnel
- training effectiveness
- department comparison

The **skill supply against drive demand** report is especially important for placement/training planning.

---

# 6. Company JD Workflow

This is a major product flow and should be visible in the UI.

```text
Placement Officer
      ↓
Create Placement Drive
      ↓
Upload / Paste Company JD
      ↓
JD Processing
      ↓
Extract Role + Skills + Eligibility + Requirements
      ↓
Map Skills to Institutional Skill Taxonomy
      ↓
Create Company Skill Requirements
      ↓
Run Matching
      ↓
Compare against Student Skill Profiles
      ↓
Eligibility + Readiness / Compatibility
      ↓
Skill Gaps
      ↓
Preparation Plans
```

The JD processing layer may initially be deterministic/manual-assisted rather than AI-powered.

Do not call the system "AI-powered" unless an actual AI implementation is present.

---

# 7. Compatibility Percentage

The UI should support a percentage such as:

```text
Backend Engineer
Compatibility: 76%
Eligibility: Eligible
```

But this percentage is a **proposed implementation feature**, not a percentage formula specified by the source document.

A possible implementation model is:

```text
Compatibility =
Σ(skill_match × skill_weight) / Σ(skill_weight) × 100
```

Example:

```text
Django       25%
PostgreSQL   20%
REST APIs    20%
Docker       15%
DSA          10%
Redis        10%
```

The actual formula, weighting, normalization, and treatment of verified/unverified evidence must be configurable and documented once implemented.

Never hard-code the example values above as if they came from the project specification.

---

# 8. Eligibility vs Readiness

This distinction is fundamental.

### Eligibility

Hard requirements:

```text
CGPA >= required value
Correct branch
No active backlogs
Graduation year
Other company criteria
```

Output:

```text
Eligible
Not Eligible
```

with reasons.

### Readiness / Compatibility

Role-specific evidence comparison:

```text
Django
PostgreSQL
REST APIs
Docker
DSA
Project Depth
Communication
Aptitude
```

Output:

```text
76% Compatibility
```

plus explanation and gaps.

Possible states:

```text
Eligible + Ready
Eligible + Not Ready
Not Eligible + Strong Skill Match
Not Eligible + Weak Skill Match
```

The system must allow these states because eligibility and readiness are independent.

---

# 9. Student Dashboard

The student dashboard should be centered around:

### Top summary cards

```text
Profile Completion
Verified Evidence
Eligible Drives
Average Readiness
```

### Main sections

1. Skill Profile
2. Upcoming Placement Drives
3. Role-specific readiness
4. Skill gaps
5. Preparation plan
6. Evidence
7. Recent activity

Example:

```text
Your Skill Profile

Python       █████████░ 90%
Django       ████████░░ 75%
PostgreSQL   ███████░░░ 70%
REST APIs    ████████░░ 80%
Docker       ████░░░░░░ 45%
DSA          ███████░░░ 70%
```

Upcoming drives:

```text
Groww — Backend Engineer       78%
Amazon — SDE Intern            72%
Microsoft — Software Engineer  65%
```

Clicking a drive should show:

- eligibility
- readiness
- required skills
- current skill level
- gaps
- preparation plan

---

# 10. Placement Officer Dashboard

The officer dashboard should focus on institutional and drive-level analytics.

### Top summary cards

```text
Total Students
Active Drives
Eligible Students
Average Readiness
```

### Batch readiness

Show distribution such as:

```text
80–100%
60–80%
40–60%
<40%
```

### Skill supply vs demand

For a selected drive:

```text
Required Skill      Student Supply
Django               72%
PostgreSQL           68%
REST APIs            64%
Docker               42%
System Design        35%
```

### Recent drives

Show:

- company
- role
- eligible students
- average readiness
- status

### Drive details

For a company JD:

```text
Company: Groww
Role: Backend Engineer

Eligibility:
✓ CGPA requirement
✓ Branch requirement
✓ Backlog requirement

Required Skills:
Django
PostgreSQL
REST APIs
Docker
System Design
DSA

Matching:
Total Students: 1245
Eligible: 862
High Match: 210
Average Readiness: 72%
```

These numbers are mock UI values only.

---

# 11. Recruiter Dashboard

Recruiters must see only the data approved for their drive.

Example:

```text
Groww — Backend Engineer

Candidates
----------------------------------------
Name       Readiness    Key Skills
Student A  86%          Django, SQL, Docker
Student B  81%          Django, PostgreSQL
Student C  78%          Python, Django, REST
```

Do not expose unrelated student records.

Do not expose fields that are not approved for release.

---

# 12. Recommended Navigation

## Student

```text
Dashboard
My Profile
Skills & Evidence
Placement Drives
Assessments
Preparation Plan
Progress
Settings
```

## Placement Officer

```text
Dashboard
Placement Drives
Students
Batch Analytics
Reports
Manage Skills
Settings
```

## Recruiter

```text
Dashboard
My Drives
Candidates
Candidate Details
```

---

# 13. Architecture

Use a **Django modular monolith**.

```text
Clients
├── Student Portal
├── Placement Portal
└── Recruiter Portal

                ↓

Django + DRF

├── Skill Taxonomy
├── Evidence Ingestion
├── Evidence Verification
├── Student Skill Profile
├── Assessment / Mock Interview
├── Readiness Engine
├── Drive & Eligibility
├── Match & Gap Analysis
├── Preparation Planning
└── Recruiter / Reporting

                ↓

PostgreSQL

Redis → Celery Workers → PostgreSQL
```

Do not introduce microservices unless there is a demonstrated requirement.

The project is explicitly suited to a Django modular monolith.

---

# 14. Technology Stack

## Backend

- Python
- Django
- Django REST Framework
- PostgreSQL

## Search / Matching

Use PostgreSQL:

- `SearchVector`
- `SearchRank`
- `pg_trgm`

Use taxonomy relationships for semantic skill expansion.

Only introduce a dedicated search engine if PostgreSQL proves insufficient.

## Background Processing

- Celery
- Redis

Typical workflow:

```text
Django API
    ↓
Create Background Task
    ↓
Redis
    ↓
Celery Worker
    ↓
Process / Compute
    ↓
PostgreSQL
```

Use Celery for:

- evidence ingestion
- readiness recomputation
- batch readiness computation
- large matching jobs
- scheduled tasks where required

Batch readiness for a 5,000-student cohort must run as a background job.

---

# 15. Suggested Domain Models

The source specification identifies these core entities:

```text
Skill
SkillSynonym
SkillCluster
Student
EvidenceItem
Verification
Assessment
MockInterview
SkillProfile
ReadinessSnapshot
Drive
DriveRequirement
EligibilityRule
Registration
GapAnalysis
PreparationPlan
RecruiterAccessGrant
AccessLog
```

Additional implementation models can be introduced when necessary, but avoid unnecessary duplication.

---

# 16. API Structure

The project specification identifies these API areas:

```text
/skills/*
/students/:id/profile
/students/:id/readiness
/drives/*
/drives/:id/match
/preparation-plans
/recruiter/*
```

Use DRF serializers and permission classes.

Keep business logic out of serializers where it becomes difficult to test.

Prefer service/domain-layer functions for:

- readiness calculation
- matching
- eligibility
- gap generation
- preparation-plan generation
- JD processing

---

# 17. Recruiter Security

This is the highest-risk surface.

Implement two independent protections:

### Layer 1 — Queryset filtering

The recruiter must only retrieve students registered for their approved drive.

Conceptually:

```python
queryset = Student.objects.filter(
    registrations__drive=approved_drive
)
```

Do not rely on frontend filtering.

### Layer 2 — Serializer field restriction

Even for an allowed student, only approved fields should be serialized.

### Access grant

Every recruiter grant should have:

```text
recruiter
drive
allowed_fields
expires_at
status
```

Expiry must be checked in the permission layer, not merely in a template.

### Logging

Log recruiter access.

### Explicit security test

There must be a negative test proving:

> A recruiter cannot access a student who is not registered for the recruiter's approved drive.

No bulk export endpoint.

---

# 18. Evidence Trust Model

Use evidence provenance.

Example:

```text
GitHub Project
    ↓
Evidence Item
    ↓
Faculty Review
    ↓
Verified
    ↓
Skill Claim
    ↓
Readiness
```

Unverified evidence can be displayed as unverified and should not silently receive the same treatment as verified institutional evidence if the implemented scoring policy distinguishes them.

Keep the distinction visible to users.

---

# 19. Readiness Computation

Readiness should be explainable.

At minimum, expose dimension-level results:

```text
Technical Mastery     78%
Aptitude              72%
Communication         68%
Project Depth         84%
```

The exact formula is not specified by the source document.

Therefore:

- make scoring configurable
- store a readiness snapshot
- store enough metadata to explain the result
- never pretend an arbitrary formula came from the project specification

When new evidence is added, readiness recomputation should be triggered, preferably debounced.

---

# 20. Gap Analysis

A gap should be specific and actionable.

Bad:

```text
Improve backend.
```

Good:

```text
Docker
Current: Beginner
Required: Intermediate
Impact: High
Suggested action: Docker fundamentals + containerize one existing project
```

The source requires ranked, actionable gaps.

The frontend should order gaps by impact.

---

# 21. Preparation Planner

Convert gaps into dated checkpoints.

Example:

```text
Week 1
- Docker fundamentals
- Dockerize existing Django project

Week 2
- PostgreSQL indexing
- Query optimization

Week 3
- REST API design
- Authentication / authorization

Week 4
- Backend mock interview
- System design practice
```

The plan should have:

- task
- resource
- start date
- due date
- checkpoint
- completion state

---

# 22. Placement Drive Flow

```text
Placement Officer
        ↓
Create Drive
        ↓
Upload JD
        ↓
Process JD
        ↓
Map Requirements
        ↓
Configure Eligibility
        ↓
Publish Drive
        ↓
Students View Drive
        ↓
Eligibility Check
        ↓
Student Registration
        ↓
Batch Matching
        ↓
Readiness / Compatibility
        ↓
Gap Analysis
        ↓
Shortlist
        ↓
Recruiter Access
```

---

# 23. Batch Analytics

Placement Officer / Placement Head should be able to see:

### Readiness distribution

```text
80–100%
60–80%
40–60%
<40%
```

### Skill supply vs demand

```text
Drive requires:

Django       → 80%
PostgreSQL   → 75%
Docker       → 60%
System Design→ 50%

Current student supply:

Django       → 72%
PostgreSQL   → 65%
Docker       → 40%
System Design→ 31%
```

### Other reports

- gap frequency across cohort
- verification coverage
- drive conversion funnel
- training effectiveness
- department comparison

---

# 24. Notifications

The specification calls for notifications around:

- new drive matching profile
- eligibility met/missed with reason
- verification requested/completed
- preparation checkpoint due
- shortlist result
- low-readiness nudges to student and mentor

Implement notifications through a service so channels can later include:

```text
in-app
email
SMS
```

---

# 25. Third-Party Integrations

Potential integrations identified by the specification:

- ERP / SIS → academics
- LMS → assessments
- coding assessment platforms such as HackerRank / Codility
- certification verification
- email
- SMS
- SSO

For the first implementation, prioritize the integrations actually required for the demo.

Do not build every integration before the core workflow works.

---

# 26. UI / UX Direction

The UI should be:

- modern
- clean
- professional
- dashboard-oriented
- data-dense without being cluttered
- suitable for a university placement system

Use:

- cards
- tables
- progress bars
- readiness charts
- skill breakdowns
- gap lists
- calendar preparation plans
- filters
- search
- clear status badges

Avoid excessive gradients, gimmicky animations, and unnecessary decorative elements.

The important information should be immediately visible.

---

# 27. Figma Mockup Screens

Create at least these screens.

## Student

1. Login
2. Student Dashboard
3. My Profile
4. Skills & Evidence
5. Evidence Detail / Verification Status
6. Placement Drives
7. Drive Details
8. Readiness / Compatibility
9. Skill Gap Analysis
10. Preparation Plan
11. Progress

## Placement Officer

1. Officer Dashboard
2. Placement Drives
3. Create Drive
4. Upload / Paste JD
5. JD Requirements Review
6. Drive Details
7. Student Matching
8. Student Details
9. Batch Analytics
10. Skill Supply vs Demand
11. Reports
12. Manage Skills

## Recruiter

1. Recruiter Dashboard
2. Approved Drive
3. Candidate Search
4. Candidate Profile
5. Controlled Evidence View

---

# 28. Main Dashboard Narrative

### Student dashboard

The student should immediately answer:

> "Where do I stand?"

Show:

```text
My Readiness
Eligible Drives
Skill Strengths
Skill Gaps
Upcoming Preparation Tasks
```

### Placement Officer dashboard

The officer should immediately answer:

> "How ready is my batch for the upcoming drives?"

Show:

```text
Students
Active Drives
Eligibility
Average Readiness
Readiness Distribution
Skill Supply vs Demand
Top Skill Gaps
```

---

# 29. Recommended Development Order

Do not start with every feature at once.

## Phase 1 — Foundation

```text
Django project
DRF
PostgreSQL
Authentication
RBAC
Base models
Docker
Environment configuration
```

## Phase 2 — Taxonomy

```text
Skill
SkillSynonym
SkillCluster
Role mappings
Taxonomy admin UI
```

## Phase 3 — Evidence

```text
EvidenceItem
Verification
Student profile
Project evidence
GitHub/external evidence structure
Faculty verification
```

## Phase 4 — Skill Profile

```text
Evidence → Skill Claims
Skill levels
Evidence provenance
Profile dashboard
```

## Phase 5 — Assessment

```text
Assessment
MockInterview
Rubrics
History
```

## Phase 6 — Readiness

```text
Readiness dimensions
Readiness snapshots
Explainability
Recomputation
```

## Phase 7 — Drives + JD

```text
Drive
DriveRequirement
EligibilityRule
JD upload
JD processing
Skill requirement mapping
```

## Phase 8 — Matching

```text
Profile vs Drive
Taxonomy expansion
Compatibility
Gap Analysis
```

## Phase 9 — Preparation

```text
Gap → Preparation Plan
Milestones
Calendar
Progress
```

## Phase 10 — Placement Analytics

```text
Batch readiness
Skill supply/demand
Shortlists
Reports
```

## Phase 11 — Recruiter Portal

```text
Access grants
Scoped queryset
Field-level serializers
Expiry
Throttling
Logging
Security tests
```

## Phase 12 — Polish

```text
Dashboard UX
Charts
Notifications
Testing
Docker
CI/CD
Documentation
```

---

# 30. Testing Requirements

At minimum, test:

## Eligibility

- eligible student
- ineligible student
- multiple eligibility rules
- explanation of failed criteria

## Matching

- exact skill match
- synonym match
- taxonomy-expanded match
- missing skill
- partial match

## Evidence

- student submission
- faculty verification
- rejected evidence
- unverified evidence

## Readiness

- readiness after new evidence
- dimension-level calculations
- readiness recomputation
- snapshot consistency

## Preparation

- gap creation
- plan generation
- checkpoint dates
- progress updates

## Recruiter Security

Mandatory:

```text
Recruiter A + Drive A
        ↓
Can access registered students in Drive A

Recruiter A + Drive A
        ↓
Cannot access Student registered only for Drive B
```

Also test:

- expired grant
- unapproved field
- unauthorized drive
- direct API access
- throttling
- access logging

---

# 31. Acceptance Criteria

The finished implementation should satisfy the project's specified outcomes:

- Skill profile assembled from at least four evidence types with verification status visible.
- Eligibility and readiness displayed independently.
- Gap analysis produces ranked, specific, actionable gaps for any student against any drive.
- Preparation plan contains dated checkpoints.
- Recruiter cannot access students outside the approved drive, proven by negative tests.
- Recruiter access is logged and reviewable.
- Batch readiness for 5,000 students runs as a background job and meets the specified performance target.
- Skill supply-against-demand report is available for a real drive.
- Taxonomy supports at least three target roles:
  - software development
  - data
  - testing

---

# 32. Non-Functional Requirements

Prioritize:

### Security

- strict RBAC
- object-level authorization
- recruiter field-level release
- access logging
- expiring grants
- throttling
- no bulk export

### Performance

- background batch readiness
- debounced readiness recomputation
- indexed PostgreSQL queries
- PostgreSQL full-text/fuzzy search
- avoid N+1 queries

### Maintainability

- modular Django apps
- service/domain layer for core computations
- serializers for API representation
- reusable permission classes
- unit + integration tests

### Explainability

Every readiness result should be explainable through:

```text
requirements
+
evidence
+
skill claims
+
assessment results
=
readiness
```

---

# 33. Important Implementation Rules

1. **Do not conflate eligibility and readiness.**
2. **Do not treat external platform activity as automatic expertise.**
3. **Do not build a Codolio clone.** The unified developer profile is supporting evidence for the placement-readiness platform.
4. **Do not invent a documented readiness formula.** If implementing one, clearly define it as an implementation choice.
5. **Do not claim AI exists unless it is actually implemented.**
6. **Do not expose recruiter data outside the approved drive.**
7. **Do not rely on frontend checks for authorization.**
8. **Do not put recruiter authorization only in templates.**
9. **Do not add microservices without a concrete requirement.**
10. **Do not build every third-party integration before the core workflow works.**
11. **Keep mock/demo numbers clearly distinguishable from real data.**
12. **Prefer explainable matching over an opaque score.**
13. **Keep the institutional skill taxonomy as the central vocabulary for matching.**
14. **Keep verification status visible throughout the evidence → skill → readiness pipeline.**

---

# 34. Core User Journey

The complete product story should be understandable as:

```text
PLACEMENT OFFICER
      │
      ├── Upload Company JD
      │
      ▼
Company Requirements
      │
      │
      │                         STUDENT
      │                            │
      │                       Add Evidence
      │                            │
      │                            ▼
      │                    Verify / Curate Evidence
      │                            │
      │                            ▼
      │                    Student Skill Profile
      │                            │
      └──────────────┬─────────────┘
                     ▼
               MATCHING ENGINE
                     │
            ┌────────┴────────┐
            ▼                 ▼
       ELIGIBILITY        READINESS
            │                 │
            │                 ▼
            │             COMPATIBILITY
            │                 │
            │                 ▼
            │             SKILL GAPS
            │                 │
            │                 ▼
            │          PREPARATION PLAN
            │
            ▼
       REGISTRATION
            │
            ▼
        SHORTLIST
            │
            ▼
      RECRUITER ACCESS
```

This is the primary end-to-end business workflow.

---

# 35. Final Product Positioning

The product should be described as:

> **An evidence-based placement readiness platform that converts fragmented student evidence into verified skill profiles, evaluates students against specific placement roles, identifies skill gaps, and generates actionable preparation plans while giving placement teams batch-level readiness analytics and recruiters controlled access to approved candidates.**

The key transition is:

> **"Am I eligible?" → "Am I ready for this specific role, and what do I need to improve?"**

---

# 36. Source-of-Truth Rule

The original P06 project specification is the source of truth for required functionality.

If a future implementation decision conflicts with the specification:

1. Preserve the documented requirement.
2. Explicitly identify the implementation decision.
3. Do not present an implementation choice as if it were part of the original specification.

In particular, the specification supports:

- multi-source evidence
- verification
- skill taxonomy
- readiness dimensions
- drive-specific matching
- gap analysis
- preparation planning
- batch analytics
- controlled recruiter access

It does **not** prescribe an exact mathematical compatibility-percentage formula.

---

# 37. Definition of Done

The project is not considered complete merely because the CRUD screens work.

A complete demo should allow this scenario end-to-end:

```text
1. Placement Officer creates a drive.
2. Officer uploads/pastes a company JD.
3. System extracts/maps requirements.
4. Students have evidence-backed skill profiles.
5. Evidence verification is visible.
6. System evaluates eligibility independently.
7. System calculates role-specific readiness/compatibility.
8. Officer sees matching students.
9. Student sees their gaps.
10. Student receives a preparation plan.
11. Officer sees batch skill supply vs drive demand.
12. Recruiter gets scoped access.
13. Unauthorized recruiter access is blocked and tested.
14. All major flows have automated tests.
```

The final demo should tell one coherent story rather than showing disconnected CRUD modules.
