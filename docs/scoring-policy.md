# Scoring policy (implementation choice)

> The P06 specification names the readiness **dimensions** (technical mastery, aptitude, communication, project depth) and requires readiness to be **explainable** and gaps to be **ranked and actionable**. It does **not** define any formula, weight or threshold.
> Everything below is this implementation's documented choice. It is configurable per institution, and versioned so old results stay explainable. None of these numbers comes from the specification.

All of these settings are editable in the app under **Placement → Scoring & Rubrics** (administrators), or via `/api/v1/readiness/config/` and `/api/v1/readiness/evidence-rules/`.

## 1. Proficiency scale

`0 None · 1 Beginner · 2 Intermediate · 3 Advanced · 4 Expert`. The same scale is used for evidence tags, skill claims, drive requirements and gaps.

## 2. From evidence to skill claims (M4)

Each evidence item tags skills with a **claimed level**. An **evidence rule** caps what each source type can establish:

| Source type | Max level if unverified | Max level if verified | Notes |
|---|---|---|---|
| Academic record | Advanced | Advanced | Institutional (recorded by staff, verified on creation) |
| Project | Intermediate | Expert | |
| Certification | Beginner | Advanced | |
| Assessment | Expert | Expert | Institutional |
| Mock interview | Advanced | Advanced | Institutional |
| GitHub / LeetCode / CodeChef / Codeforces | **Beginner** | Advanced | External activity is evidence, not proof (AGENTS.md §3) |
| Other | Beginner | Intermediate | |

- `effective level = min(claimed level, cap for the item's source and verification state)`.
- Rejected evidence is ignored.
- A **skill claim** stores two values:
  - `level`: the best effective level from any evidence.
  - `verified_level`: the best from verified evidence only.

  The difference stays visible in the UI ("Verified to Intermediate").
- So "500 LeetCode problems" can establish at most *Beginner* DSA until a mentor verifies it or an institutional assessment measures it.

Assessment percentages map to levels as: `<40 Beginner · 40–69 Intermediate · 70–89 Advanced · ≥90 Expert`.

## 3. Credited level

When scoring, the verified part of a level counts fully, and the part supported only by unverified evidence counts at the **unverified multiplier** (default **0.5**):

```
credited = verified_level + multiplier × (level − verified_level)
```

## 4. Compatibility for a drive (M8)

A student skill **satisfies** a requirement if it is the required skill, or lies below it in the taxonomy (React satisfies "Frontend Framework"). Synonyms are resolved to canonical skills when evidence is tagged.

```
credit_i      = min(best credited level among satisfying skills / required_level_i, 1)
compatibility = Σ credit_i × weight_i / Σ weight_i × 100
```

Weights and required levels come from the drive's requirements. These are set from the JD extraction, a role template or by hand.

## 5. Readiness (M6)

Five dimensions, each 0–100. Defaults are shown in brackets. The P06 specification names the first four; **coding activity is an implementation addition** requested for this project (§9).

| Dimension | General readiness | Readiness for a drive |
|---|---|---|
| Technical mastery | Mean credited level of the student's top **N** non-category skills [N = 8], as % of Expert | The drive's **compatibility** (§4) |
| Aptitude | Mean of the latest **K** aptitude assessments [K = 3] | same |
| Communication | Mean of the latest **K** communication assessments and mock-interview communication scores | same |
| Project depth | `min(1, Σ project points / target) × 100`. A project scores `(1 if verified else multiplier) × min(skills tagged, 3)/3` [target = 3] | same |
| Coding activity | Mean of the student's synced GitHub, LeetCode and Codeforces ratings (§9); 0 when none is linked or synced | same |

```
overall = Σ weight_d × score_d / Σ weight_d     weights [technical 40, aptitude 20, communication 20, project depth 20, coding activity 10]
```

- **Missing evidence scores 0.** Readiness reflects only what has been demonstrated, and each empty dimension says what to add.
- **Ready** means `overall ≥ ready threshold` [70]. Readiness is never combined with eligibility.
- Each **snapshot** stores the five scores, the overall score, the config version, and an explanation listing every input (skills, assessments, projects). Snapshots are immutable.

## 6. Gaps (M8)

For each requirement with `credit < 1`:

| Kind | When | Suggested action |
|---|---|---|
| No evidence | No satisfying skill | Learn it (with concrete examples from the taxonomy, e.g. React or Vue for "Frontend Framework"), use it in a project, add evidence |
| Below required level | `level < required` | Take it from current to required; larger project or institutional assessment |
| Not verified | `level ≥ required` but credit < 1 because of unverified evidence | Ask the mentor to verify, or take an assessment |

```
impact score = weight × (1 − credit) × (1.5 if mandatory else 1)
impact       = High if score ≥ 2, Medium if ≥ 0.75, else Low; mandatory raises it one band
```

Gaps are ranked by impact score.

## 7. Preparation plan (M9)

- **Timeline:** from today to the day before the drive (or 28 days if the drive has no date).
- **Days per gap:** about 7 days per level to climb, 2 days for a verification-only gap. Durations are scaled down proportionally when time is short, with a minimum of 3 days per gap.
- **Order:** highest impact first.
- **Items per gap:** a *Learn* task (with the best matching learning resource), an *Apply* task, and a dated **Checkpoint**.
- Celery Beat sends a reminder the day before each checkpoint.

## 8. Recomputation

- **After a change:** any evidence change or verification schedules a profile + readiness recompute, **debounced** (default 30 s; 5 s in dev). The same task refreshes the student's results for every active drive.
- **Batch:** the batch-readiness job rebuilds every student's claims and readiness, then rematches every active drive.
- **Measured** on the development machine: **5,000 students in 14.0 s** (24.7 s including one active-drive rematch), against the specification's 15-minute target.

## 9. Coding activity ratings (GitHub, LeetCode, Codeforces)

An implementation choice, added at the project owner's request. Not part of the P06 specification.

**Sources.** Students link usernames, not URLs, so the server only ever calls three fixed hosts:
- **GitHub:** the official REST API (`/users/{u}`, `/users/{u}/repos`, `/users/{u}/events/public`). It allows 60 unauthenticated requests per hour; setting `GITHUB_TOKEN` raises that limit.
- **LeetCode:** its public GraphQL endpoint. **This is unofficial and undocumented.** It can change or start rate-limiting without notice, and the UI labels LeetCode figures as coming from an unofficial source.
- **Codeforces:** the official public API (`user.info`, `user.rating`, `user.status`). It allows about one call every two seconds, so the three calls for a profile are spaced 2.1 s apart. An unknown handle is reported as "profile not found".
- **CodeChef** has no official public API, so it stays a manually added evidence item (no scraping).

**Sync.**
- Sync runs on the Celery worker when a handle is set.
- A manual refresh is allowed at most once per 30 minutes.
- Celery Beat re-syncs profiles older than a day, in batches of 40 every 6 hours.
- If a platform can't be reached, the last good rating is kept and the error is shown. If the profile doesn't exist, its rating and evidence are removed.

**Ratings (0–100).** Each rating is a weighted sum of saturating components: `points = 100 × weight × min(1, value / cap)`. That way no single huge number can dominate the rating, and every component is shown to the student.

| Platform | Component | Cap | Weight |
|---|---|---|---|
| GitHub | Push events in the last 90 days | 30 | 0.35 |
| | Original (non-fork) repositories | 10 | 0.25 |
| | Languages across repositories | 5 | 0.20 |
| | Repositories pushed in the last 90 days | 5 | 0.10 |
| | Stars received, `log10(1 + stars)` | 2 (≈ 99 stars) | 0.10 |
| LeetCode | Solved, weighted easy×1, medium×2, hard×3 | 600 | 0.70 (1.0 with no contest history) |
| | Contest rating above 1200 | 1000 | 0.30 |
| Codeforces | Distinct problems solved (accepted at least once) | 300 | 0.45 (0.70 when unrated) |
| | Problems with a problem rating of 1600+ solved | 50 | 0.20 (0.30 when unrated) |
| | Contest rating above 800 | 1200 | 0.35 (dropped when unrated) |

**Evidence, not proof.**
- Each synced profile becomes one evidence item of type GitHub, LeetCode or Codeforces. It is **self-reported** unless a mentor verifies it, and it is updated in place on every re-sync.
- LeetCode or Codeforces solved count lets the student *claim* a DSA level (≥50 solved → Intermediate, ≥200 → Advanced, ≥500 → Expert).
- GitHub languages claim Beginner, or Intermediate when used in 3 or more repositories.
- The §2 evidence-rule caps still apply, so unverified external activity counts at Beginner by default. For example, 500 LeetCode problems do **not** make a student an Expert in DSA.
- Faculty verification attests that the account belongs to the student, so verification survives a re-sync.

**Weight.** The coding-activity dimension weighs 10 by default. Administrators change it as `weight_coding` under Scoring & Rubrics, like every other weight.

