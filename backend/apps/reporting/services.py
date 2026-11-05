"""M10 batch analytics. All numbers are computed from stored data; nothing is hard-coded."""

from collections import Counter, defaultdict

from django.db import transaction
from django.db.models import Avg, Count, Max, Q

from apps.core.models import BackgroundJob
from apps.drives.models import ACTIVE_STATUSES, Drive, EligibilityResult, Registration, RegistrationStatus
from apps.evidence.models import EvidenceItem, VerificationStatus
from apps.matching.models import GapItem, MatchResult
from apps.notifications.services import notify
from apps.planning.models import ItemStatus, PlanItem, PlanStatus
from apps.profiles.models import SkillClaim
from apps.readiness import services as readiness_services
from apps.readiness.models import ReadinessSnapshot
from apps.students.models import StudentProfile
from apps.taxonomy.models import Level, SkillClosure

BANDS = [("80–100%", 80, 101), ("60–80%", 60, 80), ("40–60%", 40, 60), ("<40%", 0, 40)]
CHUNK_SIZE = 500


def band_of(score):
    for label, low, high in BANDS:
        if low <= score < high:
            return label
    return BANDS[-1][0]


def distribution(scores):
    counts = Counter(band_of(s) for s in scores)
    total = len(scores)
    return [
        {
            "band": label,
            "count": counts.get(label, 0),
            "percent": round(100 * counts.get(label, 0) / total, 1) if total else 0.0,
        }
        for label, _, _ in BANDS
    ]


# --- batch readiness -------------------------------------------------------------------------


def run_batch_readiness(institution_id, *, job=None, nudge_below=40):
    """Recompute skill claims and general readiness for every student of an institution, in
    chunks, then nudge low-readiness students and their mentors (P06 §11)."""
    from apps.profiles.services import build_claims

    students = list(StudentProfile.objects.filter(institution_id=institution_id).select_related("user", "mentor"))
    if job is not None:
        job.total = len(students)
        job.save(update_fields=["total"])
    scores = []
    nudged = 0
    for start in range(0, len(students), CHUNK_SIZE):
        chunk = students[start : start + CHUNK_SIZE]
        with transaction.atomic():
            build_claims(chunk)
            snapshots = readiness_services.compute_snapshots(chunk)
        for student, snap in zip(chunk, snapshots, strict=True):
            overall = float(snap.overall)
            scores.append(overall)
            if nudge_below is not None and overall < nudge_below:
                _nudge(student, overall)
                nudged += 1
        if job is not None:
            job.processed = min(start + CHUNK_SIZE, len(students))
            job.save(update_fields=["processed"])
    # Profiles changed, so drive-specific results must be recomputed too.
    from apps.matching.services import run_drive_matching

    drives = list(Drive.objects.filter(institution_id=institution_id, status__in=ACTIVE_STATUSES))
    for drive in drives:
        run_drive_matching(drive)
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {
        "students": len(students),
        "average_readiness": avg,
        "distribution": distribution(scores),
        "nudged": nudged,
        "drives_rematched": len(drives),
    }


def _nudge(student, overall):
    notify(
        student.user,
        kind="low_readiness",
        title=f"Your readiness is {overall:.0f}%",
        body="Open your dashboard to see which evidence and assessments would raise it.",
        link="/student",
    )
    if student.mentor_id:
        notify(
            student.mentor,
            kind="low_readiness_mentee",
            title=f"{student.name}: readiness {overall:.0f}%",
            body="A mentee's readiness is low; consider a check-in.",
            link="/faculty",
        )


def start_batch_readiness_job(institution_id, created_by=None):
    from .tasks import batch_readiness_task

    job = BackgroundJob.objects.create(institution_id=institution_id, kind="batch_readiness", created_by=created_by)
    transaction.on_commit(lambda: batch_readiness_task.delay(job.pk))
    return job


# --- reports ---------------------------------------------------------------------------------


def overview(institution_id):
    students = StudentProfile.objects.filter(institution_id=institution_id)
    student_ids = list(students.values_list("pk", flat=True))
    latest = readiness_services.latest_general_overall(student_ids)
    active = Drive.objects.filter(institution_id=institution_id, status__in=ACTIVE_STATUSES)
    eligible_students = (
        EligibilityResult.objects.filter(drive__in=active, is_eligible=True).values("student_id").distinct().count()
    )
    scores = list(latest.values())
    recent = []
    for d in Drive.objects.filter(institution_id=institution_id).select_related("company").order_by("-created_at")[:6]:
        agg = MatchResult.objects.filter(drive=d).aggregate(
            avg=Avg("compatibility"), readiness=Avg("readiness_overall")
        )
        recent.append(
            {
                "id": d.pk,
                "company": d.company.name,
                "role": d.role_title,
                "status": d.status,
                "status_label": d.get_status_display(),
                "eligible": EligibilityResult.objects.filter(drive=d, is_eligible=True).count(),
                "registered": Registration.objects.filter(drive=d).exclude(status=RegistrationStatus.WITHDRAWN).count(),
                "average_compatibility": round(float(agg["avg"]), 1) if agg["avg"] is not None else None,
                "average_readiness": round(float(agg["readiness"]), 1) if agg["readiness"] is not None else None,
                "matched": d.last_matched_at is not None,
            }
        )
    return {
        "total_students": len(student_ids),
        "students_with_readiness": len(scores),
        "active_drives": active.count(),
        "eligible_students": eligible_students,
        "average_readiness": round(sum(scores) / len(scores), 1) if scores else None,
        "readiness_distribution": distribution(scores),
        "recent_drives": recent,
        "top_gaps": gap_frequency(institution_id, limit=5),
    }


def supply_demand_for_drive(drive, population="all"):
    """For each requirement: % of students whose profile meets the required level (supply), and
    % meeting it with verified evidence. `population` = all | eligible."""
    requirements = list(drive.requirements.select_related("skill__cluster"))
    students = StudentProfile.objects.filter(institution_id=drive.institution_id)
    if population == "eligible":
        students = students.filter(
            pk__in=EligibilityResult.objects.filter(drive=drive, is_eligible=True).values("student_id")
        )
    student_ids = list(students.values_list("pk", flat=True))
    total = len(student_ids)
    satisfying = defaultdict(set)
    for ancestor, descendant in SkillClosure.objects.filter(
        ancestor_id__in=[r.skill_id for r in requirements]
    ).values_list("ancestor_id", "descendant_id"):
        satisfying[ancestor].add(descendant)
    best = defaultdict(lambda: defaultdict(lambda: (0, 0)))
    claims = SkillClaim.objects.filter(student_id__in=student_ids).values_list(
        "student_id", "skill_id", "level", "verified_level"
    )
    req_by_desc = defaultdict(list)
    for r in requirements:
        for d in satisfying[r.skill_id]:
            req_by_desc[d].append(r.skill_id)
    for sid, skill_id, level, verified in claims:
        for req_skill in req_by_desc.get(skill_id, ()):
            lv, vv = best[req_skill][sid]
            best[req_skill][sid] = (max(lv, level), max(vv, verified))
    weight_total = sum(r.weight for r in requirements) or 1
    rows = []
    for r in requirements:
        levels = best[r.skill_id].values()
        meets = sum(1 for lv, _ in levels if lv >= r.required_level)
        verified = sum(1 for _, vv in levels if vv >= r.required_level)
        any_evidence = sum(1 for lv, _ in levels if lv > 0)
        rows.append(
            {
                "skill_id": r.skill_id,
                "skill": r.skill.name,
                "required_level": Level(r.required_level).label,
                "is_mandatory": r.is_mandatory,
                "weight": r.weight,
                "demand_share": round(100 * r.weight / weight_total, 1),
                "supply_percent": round(100 * meets / total, 1) if total else 0.0,
                "verified_supply_percent": round(100 * verified / total, 1) if total else 0.0,
                "any_evidence_percent": round(100 * any_evidence / total, 1) if total else 0.0,
                "shortfall_students": total - meets,
                "cluster": r.skill.cluster.slug if r.skill.cluster_id else None,
            }
        )
    rows.sort(key=lambda x: x["supply_percent"])
    return {
        "drive_id": drive.pk,
        "drive": str(drive),
        "population": population,
        "students": total,
        "requirements": rows,
    }


def demand_across_drives(institution_id):
    """Skill demand across active drives vs current supply: what training should cover next."""
    active = Drive.objects.filter(institution_id=institution_id, status__in=ACTIVE_STATUSES)
    demand = defaultdict(lambda: {"drives": 0, "max_required": 0, "skill": "", "cluster": None})
    for d in active.prefetch_related("requirements__skill__cluster"):
        for r in d.requirements.all():
            row = demand[r.skill_id]
            row["drives"] += 1
            row["max_required"] = max(row["max_required"], r.required_level)
            row["skill"] = r.skill.name
            row["cluster"] = r.skill.cluster.slug if r.skill.cluster_id else None
    total = StudentProfile.objects.filter(institution_id=institution_id).count()
    rows = []
    for skill_id, row in demand.items():
        descendants = SkillClosure.objects.filter(ancestor_id=skill_id).values("descendant_id")
        meets = (
            SkillClaim.objects.filter(
                skill_id__in=descendants, level__gte=row["max_required"], student__institution_id=institution_id
            )
            .values("student_id")
            .distinct()
            .count()
        )
        rows.append(
            {
                "skill_id": skill_id,
                "skill": row["skill"],
                "active_drives": row["drives"],
                "required_level": Level(row["max_required"]).label,
                "supply_percent": round(100 * meets / total, 1) if total else 0.0,
                "cluster": row["cluster"],
            }
        )
    rows.sort(key=lambda x: (-x["active_drives"], x["supply_percent"]))
    return {"active_drives": active.count(), "students": total, "skills": rows}


def gap_frequency(institution_id, drive=None, limit=20):
    qs = GapItem.objects.filter(analysis__institution_id=institution_id)
    if drive is not None:
        qs = qs.filter(analysis__drive=drive)
    else:
        qs = qs.filter(analysis__drive__status__in=ACTIVE_STATUSES)
    rows = (
        qs.values("skill_id", "skill__name")
        .annotate(
            students=Count("analysis__student", distinct=True),
            # Students, not gap rows: one student can have the same gap on several drives.
            high=Count("analysis__student", distinct=True, filter=Q(impact="high")),
            missing=Count("analysis__student", distinct=True, filter=Q(kind="missing")),
            unverified=Count("analysis__student", distinct=True, filter=Q(kind="unverified")),
            cluster=Max("skill__cluster__slug"),
        )
        .order_by("-students", "skill__name")[:limit]
    )
    return [
        {
            "skill_id": r["skill_id"],
            "skill": r["skill__name"],
            "students": r["students"],
            "high_impact": r["high"],
            "missing": r["missing"],
            "unverified": r["unverified"],
            "cluster": r["cluster"],
        }
        for r in rows
    ]


def verification_coverage(institution_id):
    items = EvidenceItem.objects.filter(institution_id=institution_id)
    by_status = dict(items.values_list("verification_status").annotate(n=Count("id")))
    by_source = [
        {
            "source_type": r["source_type"],
            "total": r["total"],
            "verified": r["verified"],
            "percent_verified": round(100 * r["verified"] / r["total"], 1) if r["total"] else 0.0,
        }
        for r in items.values("source_type")
        .annotate(total=Count("id"), verified=Count("id", filter=Q(verification_status=VerificationStatus.VERIFIED)))
        .order_by("source_type")
    ]
    students = StudentProfile.objects.filter(institution_id=institution_id).count()
    with_verified = (
        items.filter(verification_status=VerificationStatus.VERIFIED).values("student_id").distinct().count()
    )
    total = sum(by_status.values())
    return {
        "total_evidence": total,
        "by_status": {s.value: by_status.get(s.value, 0) for s in VerificationStatus},
        "by_source": by_source,
        "students": students,
        "students_with_verified_evidence": with_verified,
        "student_coverage_percent": round(100 * with_verified / students, 1) if students else 0.0,
        "pending": by_status.get(VerificationStatus.PENDING, 0),
    }


def drive_funnel(drive):
    regs = Registration.objects.filter(drive=drive)
    eligible = EligibilityResult.objects.filter(drive=drive, is_eligible=True).count()
    registered = regs.exclude(status=RegistrationStatus.WITHDRAWN).count()
    shortlisted = regs.filter(
        status__in=[RegistrationStatus.SHORTLISTED, RegistrationStatus.SELECTED, RegistrationStatus.NOT_SELECTED]
    ).count()
    selected = regs.filter(status=RegistrationStatus.SELECTED).count()
    evaluated = EligibilityResult.objects.filter(drive=drive).count()
    return {
        "drive_id": drive.pk,
        "stages": [
            {"stage": "Evaluated", "count": evaluated},
            {"stage": "Eligible", "count": eligible},
            {"stage": "Registered", "count": registered},
            {"stage": "Shortlisted", "count": shortlisted},
            {"stage": "Selected", "count": selected},
        ],
    }


def department_comparison(institution_id):
    students = list(StudentProfile.objects.filter(institution_id=institution_id).select_related("department"))
    latest = readiness_services.latest_general_overall([s.pk for s in students])
    groups = defaultdict(list)
    names = {}
    for s in students:
        groups[s.department.code].append(latest.get(s.pk))
        names[s.department.code] = s.department.name
    rows = []
    for code, values in sorted(groups.items()):
        scored = [v for v in values if v is not None]
        rows.append(
            {
                "department": code,
                "name": names[code],
                "students": len(values),
                "average_readiness": round(sum(scored) / len(scored), 1) if scored else None,
                "ready_percent": round(100 * sum(v >= 70 for v in scored) / len(scored), 1) if scored else None,
            }
        )
    return rows


def training_effectiveness(institution_id):
    """Observational: readiness change between each student's first and latest general snapshot,
    split by preparation-plan engagement. Correlation, not proof of causation."""
    snaps = defaultdict(list)
    for sid, overall, _created in (
        ReadinessSnapshot.objects.filter(institution_id=institution_id, drive__isnull=True)
        .order_by("created_at")
        .values_list("student_id", "overall", "created_at")
    ):
        snaps[sid].append(float(overall))
    deltas = {sid: v[-1] - v[0] for sid, v in snaps.items() if len(v) >= 2}
    completion = {}
    for sid, total, done in (
        PlanItem.objects.filter(plan__institution_id=institution_id)
        .values("plan__student_id")
        .annotate(total=Count("id"), done=Count("id", filter=Q(status=ItemStatus.DONE)))
        .values_list("plan__student_id", "total", "done")
    ):
        completion[sid] = done / total if total else 0
    engaged = [d for sid, d in deltas.items() if completion.get(sid, 0) >= 0.5]
    others = [d for sid, d in deltas.items() if completion.get(sid, 0) < 0.5]

    def avg(values):
        return round(sum(values) / len(values), 2) if values else None

    return {
        "students_with_history": len(deltas),
        "average_change": avg(list(deltas.values())),
        "plan_engaged": {"students": len(engaged), "average_change": avg(engaged)},
        "not_engaged": {"students": len(others), "average_change": avg(others)},
        "note": "Engaged = completed at least half of their preparation-plan items. Observational comparison; "
        "differences are not proof that the plan caused the change.",
    }


def student_summaries(students):
    """One summary row per student (academics, readiness, evidence by status, drives, plan
    progress), computed with a fixed number of grouped queries. Used by the faculty mentee table
    and the staff Excel export. Readiness is the general snapshot, never mixed with eligibility."""
    students = list(students)
    ids = [s.pk for s in students]
    readiness = readiness_services.latest_general_overall(ids)
    evidence = defaultdict(Counter)
    for sid, st, n in (
        EvidenceItem.objects.filter(student_id__in=ids)
        .values_list("student_id", "verification_status")
        .annotate(n=Count("id"))
    ):
        evidence[sid][st] = n
    registrations = dict(
        Registration.objects.filter(student_id__in=ids)
        .exclude(status=RegistrationStatus.WITHDRAWN)
        .values_list("student_id")
        .annotate(n=Count("id"))
    )
    eligible = dict(
        EligibilityResult.objects.filter(student_id__in=ids, is_eligible=True, drive__status__in=ACTIVE_STATUSES)
        .values_list("student_id")
        .annotate(n=Count("id"))
    )
    plans = {
        sid: (done, total)
        for sid, done, total in PlanItem.objects.filter(plan__student_id__in=ids, plan__status=PlanStatus.ACTIVE)
        .values_list("plan__student_id")
        .annotate(done=Count("id", filter=Q(status=ItemStatus.DONE)), total=Count("id"))
    }
    rows = []
    for s in students:
        ev = evidence[s.pk]
        done, total = plans.get(s.pk, (0, 0))
        rows.append(
            {
                "id": s.pk,
                "name": s.name,
                "email": s.user.email,
                "roll_number": s.roll_number,
                "department": s.department.code,
                "graduation_year": s.graduation_year,
                "cgpa": float(s.cgpa),
                "active_backlogs": s.active_backlogs,
                "academic_record_verified": s.academic_record_verified,
                "mentor": (s.mentor.get_full_name() or s.mentor.email) if s.mentor_id else None,
                "readiness": readiness.get(s.pk),
                "evidence_total": sum(ev.values()),
                "evidence_verified": ev.get(VerificationStatus.VERIFIED, 0),
                "evidence_pending": ev.get(VerificationStatus.PENDING, 0),
                "evidence_rejected": ev.get(VerificationStatus.REJECTED, 0),
                "registrations": registrations.get(s.pk, 0),
                "eligible_drives": eligible.get(s.pk, 0),
                "plan_done": done,
                "plan_total": total,
            }
        )
    return rows
