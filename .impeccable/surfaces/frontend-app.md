---
version: 1
slug: "frontend-app"
primary_target: "frontend/app"
related_targets: []
---

# Surface brief: Placement Readiness app (all internal portals + recruiter portal)

Scope: the authenticated web app (`frontend/app`): student, faculty, placement and recruiter portals, sign-up, onboarding, account. Visitor mode: **Operate**.

Audience and job: students checking "where do I stand / what next" around drives; faculty verifying and assessing; the placement cell running drives on dense tables; recruiters browsing a scoped shortlist. Success is a task completed with no hunting. Keep: navigation and routes, separate eligibility and readiness blocks, dense officer tables. Avoid: grey corporate look, slow or showy motion, a neon dark-only "hacker" look, gamification.

New in this round: student self sign-up, an onboarding pop-up (GitHub, LinkedIn, LeetCode, resume), GitHub/LeetCode coding-activity ratings, resume upload and view, toasts, a light/dark/system theme switch, micro-interactions.

## Direction contract

THESIS: Preparation as a stack of numbered, colour-coded study modules, the coaching-booklet system every student already studied with. Refuses the grey card dashboard with one indigo accent.

OWN-WORLD: committed cobalt shell rail (#1E3FAE) on a cool practice-sheet white (#F6F7FB) or ink-navy dark ground. Five flat module hues own skill clusters: cobalt (programming/backend), teal (databases/devops), green (data), marigold (testing), crimson (CS fundamentals). Violet (#6D28D9) is reserved only for "your next step". Flat colour, no gradients or glow; one sans family (Geist); every number tabular.

STORY: the student sees where they stand (KPIs, readiness incl. coding activity), what to do next (the violet NEXT module), and each drive's eligibility and match side by side. Staff see dense, scannable tables with the same spines.

FIRST VIEWPORT: cobalt rail left with nav; header with greeting, theme segmented control and notifications; 4 KPI tiles with module-hue edge; left column of numbered module spines (gaps and plan) with checkpoints and the plan's time budget against the drive date; right column with the readiness radar (5 dimensions) and a drives table; toasts bottom-right.

FORM: candidate 7 of 7 (coaching-institute module booklets). seed:c332254880406b8c. Raises: reserved next-step hue (orienteering); tabular numerics (datamatics); hard time budget (j-card); flat colour (garden map). Signature move: numbered cluster-coloured module spines on gaps, plan items and skills. Motion grammar: 150–220 ms state transitions, toast slide, meter fill on mount, press feedback; all off under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
