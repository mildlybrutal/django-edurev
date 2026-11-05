"""Builds one coherent, fully synthetic demo: an institution, staff, a mentored cohort with mixed
evidence and assessments, drives at different stages, matching results, a preparation plan and a
recruiter grant. Uses the real services, so the demo exercises the same rules as production."""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role
from apps.assessments import services as assessment_services
from apps.assessments.models import Rubric, RubricCriterion
from apps.core.models import Institution
from apps.drives import services as drive_services
from apps.drives.models import Company, Drive, DriveStatus, RegistrationStatus, RuleType
from apps.evidence import services as evidence_services
from apps.evidence.models import EvidenceItem, EvidenceSkillTag, SourceType, VerificationStatus
from apps.matching.services import run_drive_matching
from apps.planning.models import LearningResource
from apps.planning.services import generate_plan
from apps.profiles.services import build_claims
from apps.recruiter import services as recruiter_services
from apps.reporting.services import run_batch_readiness
from apps.students.models import Department, StudentProfile
from apps.taxonomy.models import TargetRole
from apps.taxonomy.seeding import seed_taxonomy
from apps.taxonomy.selectors import resolve_skill

from .data import BACKEND_JD, DEPARTMENTS, FIRST_NAMES, LAST_NAMES, PROFILES, PROJECT_TITLES, RESOURCES

DEMO = {"code": "demo", "name": "Demo Institute (synthetic data)"}
STAFF = [
    ("admin@demo.example.test", "Asha", "Admin", Role.ADMIN),
    ("placement.head@demo.example.test", "Harpreet", "Head", Role.PLACEMENT_HEAD),
    ("placement.officer@demo.example.test", "Omar", "Officer", Role.PLACEMENT_OFFICER),
    ("faculty@demo.example.test", "Farida", "Faculty", Role.FACULTY),
    ("faculty2@demo.example.test", "Gaurav", "Faculty", Role.FACULTY),
    ("recruiter@demo.example.test", "Rhea", "Recruiter", Role.RECRUITER),
]


def _user(email, first, last, role, institution, password):
    User = get_user_model()
    user, created = User.objects.get_or_create(
        email=email, defaults={"institution": institution, "first_name": first, "last_name": last}
    )
    if created:
        user.set_password(password)
        user.save()
    user.groups.add(Group.objects.get(name=role))
    return user, created


def _skill(institution, name):
    skill = resolve_skill(institution, name)
    if skill is None:
        raise LookupError(name)
    return skill


def _rubrics(institution):
    specs = {
        "Aptitude test": ("aptitude", [("Quantitative", 20), ("Logical reasoning", 20), ("Verbal", 20)]),
        "Communication assessment": ("communication", [("Clarity", 10), ("Structure", 10), ("Listening", 10)]),
        "Technical practical": ("technical", [("Problem solving", 10), ("Correctness", 10), ("Code quality", 10)]),
    }
    rubrics = {}
    for name, (kind, criteria) in specs.items():
        rubric, created = Rubric.objects.get_or_create(institution=institution, name=name, defaults={"kind": kind})
        if created:
            RubricCriterion.objects.bulk_create(
                RubricCriterion(rubric=rubric, name=c, max_score=m, order=i) for i, (c, m) in enumerate(criteria)
            )
        rubrics[kind] = rubric
    return rubrics


def _score(rubric, rng, quality):
    """Scores for every criterion, around `quality` (0-1)."""
    return {c: round(max(0, min(c.max_score, rng.gauss(quality, 0.15) * c.max_score))) for c in rubric.criteria.all()}


def _populate_student(student, rng, institution, rubrics, mentor, *, profile, strength):
    """Evidence + assessments for one synthetic student. `strength` 0-1 shapes the levels."""
    skills = PROFILES[profile]
    for title in rng.sample(PROJECT_TITLES[profile], k=min(len(PROJECT_TITLES[profile]), 1 + int(strength * 2))):
        picked = rng.sample(skills, k=min(len(skills), rng.randint(2, 4)))
        tags = [(_skill(institution, n), max(1, min(4, round(lv * (0.6 + strength * 0.6))))) for n, lv in picked]
        item = evidence_services.submit_evidence(
            student=student,
            source_type=SourceType.PROJECT,
            title=title,
            description="Synthetic demo project.",
            source_url="https://example.test/repo",
            tags=tags,
        )
        roll = rng.random()
        if roll < 0.45 + strength * 0.3:
            evidence_services.set_status(item, VerificationStatus.VERIFIED)
        elif roll < 0.8:
            evidence_services.set_status(item, VerificationStatus.PENDING)
    if rng.random() < 0.6:
        evidence_services.submit_evidence(
            student=student,
            source_type=SourceType.LEETCODE,
            title="LeetCode profile",
            external_reference=f"demo_user_{student.pk}",
            extracted_data={"problems_solved": rng.randint(40, 450)},
            tags=[(_skill(institution, "DSA"), rng.choice([2, 3, 4]))],
        )
    if rng.random() < 0.5:
        cert_skill = rng.choice(["AWS", "Python", "SQL", "Java"])
        evidence_services.submit_evidence(
            student=student,
            source_type=SourceType.CERTIFICATION,
            title=f"{cert_skill} fundamentals certificate",
            external_reference=f"CERT-{student.pk:05d}",
            tags=[(_skill(institution, cert_skill), 2)],
            request_verification=rng.random() < 0.5,
        )
    today = timezone.localdate()
    if rng.random() < 0.85:
        assessment_services.record_assessment(
            student=student,
            rubric=rubrics["aptitude"],
            title="Aptitude test — term 1",
            assessed_by=mentor,
            assessed_on=today - timedelta(days=rng.randint(10, 60)),
            scores=_score(rubrics["aptitude"], rng, 0.45 + strength * 0.4),
        )
    if rng.random() < 0.6:
        assessment_services.record_assessment(
            student=student,
            rubric=rubrics["communication"],
            title="Communication assessment",
            assessed_by=mentor,
            assessed_on=today - timedelta(days=rng.randint(5, 40)),
            scores=_score(rubrics["communication"], rng, 0.5 + strength * 0.35),
        )
    if rng.random() < 0.5:
        main_skill = _skill(institution, skills[0][0])
        assessment_services.record_assessment(
            student=student,
            rubric=rubrics["technical"],
            title=f"{main_skill.name} practical",
            assessed_by=mentor,
            assessed_on=today - timedelta(days=rng.randint(5, 30)),
            skill=main_skill,
            scores=_score(rubrics["technical"], rng, 0.4 + strength * 0.5),
        )
    if rng.random() < 0.4:
        assessment_services.record_mock_interview(
            student=student,
            interviewer=mentor,
            conducted_on=today - timedelta(days=rng.randint(1, 20)),
            role_focus="Software engineer",
            technical_score=int(40 + strength * 50),
            communication_score=int(45 + strength * 45),
            problem_solving_score=int(40 + strength * 50),
            feedback="Synthetic mock-interview feedback.",
            skill_ratings=[(_skill(institution, skills[0][0]), max(1, round(1 + strength * 2)))],
        )


@transaction.atomic
def seed_demo(*, password, students=40, seed=42):
    rng = random.Random(seed)
    institution, _ = Institution.objects.get_or_create(
        code=DEMO["code"], defaults={"name": DEMO["name"], "allow_student_signup": True}
    )
    seed_taxonomy(institution)
    staff, created = {}, []
    for email, first, last, role in STAFF:
        user, was_created = _user(email, first, last, role, institution, password)
        staff[role] = staff.get(role) or user
        if was_created:
            created.append(email)
    faculty2 = get_user_model().objects.get(email="faculty2@demo.example.test")
    depts = {
        code: Department.objects.get_or_create(institution=institution, code=code, defaults={"name": name})[0]
        for code, name in DEPARTMENTS
    }
    for skill_name, level, title, url, kind in RESOURCES:
        LearningResource.objects.get_or_create(
            institution=institution,
            skill=_skill(institution, skill_name),
            title=title,
            defaults={"target_level": level, "url": url, "kind": kind},
        )
    rubrics = _rubrics(institution)

    if StudentProfile.objects.filter(institution=institution).exists():
        return {
            "created_accounts": created,
            "students": StudentProfile.objects.filter(institution=institution).count(),
            "note": "Cohort already present; nothing regenerated.",
        }

    # The cohort. The first student is the demo login with a good-but-incomplete backend profile.
    mentors = (staff[Role.FACULTY], faculty2)
    cohort = []
    for i in range(students):
        student, was_created = _cohort_student(i, rng, institution, depts, mentors, rubrics, password)
        if was_created and i == 0:
            created.append(student.user.email)
        cohort.append(student)

    officer, head = staff[Role.PLACEMENT_OFFICER], staff[Role.PLACEMENT_HEAD]
    now = timezone.now()

    def company(name):
        return Company.objects.get_or_create(institution=institution, name=name)[0]

    # Drive 1: JD processed and applied; published; matched; registrations; recruiter grant.
    backend = drive_services.create_drive(
        institution=institution,
        company=company("Capgemini"),
        role_title="Backend Engineer",
        created_by=officer,
        location="Bengaluru",
        compensation="Synthetic: 12 LPA",
        registration_opens_at=now - timedelta(days=2),
        registration_closes_at=now + timedelta(days=10),
        drive_date=timezone.localdate() + timedelta(days=30),
    )
    # Process the JD inline (submit_jd would also queue the same work on the worker).
    backend.job_description = BACKEND_JD
    backend.save(update_fields=["job_description"])
    drive_services.run_jd_processing(backend)
    extraction = backend.jd_extraction
    drive_services.apply_jd_extraction(
        backend,
        actor=officer,
        skills=[
            {k: s[k] for k in ("skill_id", "required_level", "weight", "is_mandatory")} for s in extraction["skills"]
        ],
        rules=[{"rule_type": r["rule_type"], "value": r["value"]} for r in extraction["eligibility"]],
    )
    backend.status = DriveStatus.PUBLISHED
    backend.save(update_fields=["status"])

    # Drive 2: from the Data Analyst role template.
    data_drive = drive_services.create_drive(
        institution=institution,
        company=company("Accenture"),
        role_title="Data Analyst",
        created_by=officer,
        target_role=TargetRole.objects.get(institution=institution, slug="data-analyst"),
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=14),
        drive_date=timezone.localdate() + timedelta(days=40),
    )
    drive_services.set_eligibility_rule(data_drive, RuleType.MIN_CGPA, 6.5)
    data_drive.status = DriveStatus.PUBLISHED
    data_drive.save(update_fields=["status"])

    # Drive 3: QA, registration closed, shortlisting in progress.
    qa = drive_services.create_drive(
        institution=institution,
        company=company("Infosys"),
        role_title="QA Engineer",
        created_by=officer,
        target_role=TargetRole.objects.get(institution=institution, slug="qa-test-engineer"),
        registration_opens_at=now - timedelta(days=20),
        registration_closes_at=now + timedelta(days=1),
        drive_date=timezone.localdate() + timedelta(days=7),
    )
    drive_services.set_eligibility_rule(qa, RuleType.MAX_ACTIVE_BACKLOGS, 1)
    qa.status = DriveStatus.PUBLISHED
    qa.save(update_fields=["status"])

    # Drive 4: draft, not visible to students.
    drive_services.create_drive(
        institution=institution,
        company=company("TCS"),
        role_title="SDE Intern",
        created_by=officer,
        target_role=TargetRole.objects.get(institution=institution, slug="software-development-engineer"),
    )

    # Build skill claims now (the worker would do it after commit) so matching sees real profiles.
    build_claims(cohort)
    for drive in (backend, data_drive, qa):
        run_drive_matching(drive)
    for drive, share in ((backend, 0.6), (data_drive, 0.4), (qa, 0.7)):
        for student in cohort:
            if student.pk == cohort[0].pk and drive is not backend:
                continue
            ok = drive.eligibility_results.filter(student=student, is_eligible=True).exists()
            if ok and (student.pk == cohort[0].pk or rng.random() < share):
                drive_services.register(drive, student)
    qa.status = DriveStatus.REGISTRATION_CLOSED
    qa.save(update_fields=["status"])
    best = qa.match_results.order_by("-compatibility").values_list("student_id", flat=True)[:5]
    for registration in qa.registrations.filter(student_id__in=list(best)):
        drive_services.decide_registration(registration, RegistrationStatus.SHORTLISTED, actor=officer)
    qa.status = DriveStatus.SHORTLISTING
    qa.save(update_fields=["status"])

    generate_plan(cohort[0], backend)
    recruiter_services.create_grant(
        recruiter=staff[Role.RECRUITER],
        drive=backend,
        granted_by=head,
        allowed_fields=[
            "name",
            "department",
            "graduation_year",
            "compatibility",
            "readiness",
            "skills",
            "evidence",
            "registration_status",
        ],
        expires_at=now + timedelta(days=14),
    )
    summary = run_batch_readiness(institution.id, nudge_below=None)
    return {
        "created_accounts": created,
        "students": len(cohort),
        "drives": 4,
        "average_readiness": summary["average_readiness"],
    }


def _cohort_student(i, rng, institution, depts, mentors, rubrics, password):
    """Student number `i` of the demo cohort (0 is the demo login), with evidence and assessments."""
    if i == 0:
        email, first, last = "student@demo.example.test", "Sana", "Student"
        dept, cgpa, backlogs, profile, strength = "CSE", Decimal("8.20"), 0, "backend", 0.55
    else:
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        email = f"student{i:03d}@demo.example.test"
        dept = rng.choices(["CSE", "IT", "ECE", "ME"], weights=[45, 30, 15, 10])[0]
        cgpa = Decimal(str(round(rng.uniform(5.6, 9.7), 2)))
        backlogs = 0 if rng.random() < 0.85 else rng.randint(1, 3)
        profile = rng.choice(list(PROFILES))
        strength = rng.random()
    user, was_created = _user(email, first, last, Role.STUDENT, institution, password)
    student = StudentProfile.objects.create(
        institution=institution,
        user=user,
        roll_number=f"1230{i + 1:04d}",
        department=depts[dept],
        graduation_year=2027 if rng.random() < 0.9 or i == 0 else 2026,
        cgpa=cgpa,
        active_backlogs=backlogs,
        mentor=mentors[i % 2],
        headline=f"{profile.title()} enthusiast" if i == 0 else "",
    )
    _populate_student(student, rng, institution, rubrics, student.mentor, profile=profile, strength=strength)
    return student, was_created


MAX_DEMO_STUDENTS = 2000  # emails are student###, roll numbers 1230####; also keeps seeding quick


@transaction.atomic
def grow_demo_cohort(*, count, seed=None):
    """Add `count` synthetic students to an existing demo, then refresh matching, open-drive
    registrations and batch readiness so dashboards and analytics include them. The new accounts
    have no usable password: only the staff accounts and student@demo.example.test sign in."""
    institution = Institution.objects.filter(code=DEMO["code"]).first()
    if institution is None or not StudentProfile.objects.filter(institution=institution).exists():
        raise ValueError("No demo cohort yet. Run seed_demo first (it accepts --students for the initial size).")
    existing = StudentProfile.objects.filter(institution=institution).count()
    if existing + count > MAX_DEMO_STUDENTS:
        raise ValueError(f"The demo is capped at {MAX_DEMO_STUDENTS} students ({existing} present).")
    rng = random.Random(seed if seed is not None else existing)
    User = get_user_model()
    depts = {d.code: d for d in Department.objects.filter(institution=institution)}
    mentors = (
        User.objects.get(email="faculty@demo.example.test"),
        User.objects.get(email="faculty2@demo.example.test"),
    )
    rubrics = _rubrics(institution)
    taken = set(StudentProfile.objects.filter(institution=institution).values_list("roll_number", flat=True))
    new, i = [], 1
    while len(new) < count:
        if f"1230{i + 1:04d}" not in taken:
            new.append(_cohort_student(i, rng, institution, depts, mentors, rubrics, None)[0])
        i += 1

    build_claims(new)
    drives = list(
        Drive.objects.filter(
            institution=institution,
            status__in=[DriveStatus.PUBLISHED, DriveStatus.REGISTRATION_CLOSED, DriveStatus.SHORTLISTING],
        )
    )
    for drive in drives:
        run_drive_matching(drive)
        if not drive_services.registration_open(drive):
            continue
        eligible = set(
            drive.eligibility_results.filter(student__in=new, is_eligible=True).values_list("student_id", flat=True)
        )
        for student in new:
            if student.pk in eligible and rng.random() < 0.5:
                drive_services.register(drive, student)
    summary = run_batch_readiness(institution.id, nudge_below=None)
    return {
        "added": len(new),
        "students": existing + len(new),
        "drives_rematched": len(drives),
        "average_readiness": summary["average_readiness"],
    }


def synthetic_cohort(institution, count, *, seed=7, chunk=1000):
    """Bulk-create `count` synthetic students with evidence for load testing (no per-row services,
    so 5,000 students take seconds). Accounts get an unusable password."""
    rng = random.Random(seed)
    seed_taxonomy(institution)
    depts = [
        Department.objects.get_or_create(institution=institution, code=c, defaults={"name": n})[0]
        for c, n in DEPARTMENTS
    ]
    skill_pool = {name: _skill(institution, name) for bundle in PROFILES.values() for name, _ in bundle}
    User = get_user_model()
    student_group = Group.objects.get(name=Role.STUDENT)
    unusable = make_password(None)
    start = StudentProfile.objects.filter(institution=institution, roll_number__startswith="99").count()
    made = 0
    while made < count:
        n = min(chunk, count - made)
        base = start + made
        users = User.objects.bulk_create(
            User(
                email=f"load{base + i:06d}@{institution.code}.example.test",
                password=unusable,
                first_name="Load",
                last_name=f"Student {base + i}",
                institution=institution,
            )
            for i in range(n)
        )
        User.groups.through.objects.bulk_create(
            User.groups.through(user_id=u.pk, group_id=student_group.pk) for u in users
        )
        profiles = StudentProfile.objects.bulk_create(
            StudentProfile(
                institution=institution,
                user=u,
                roll_number=f"99{base + i:06d}",
                department=rng.choice(depts),
                graduation_year=2027,
                cgpa=Decimal(str(round(rng.uniform(5.5, 9.8), 2))),
                active_backlogs=0 if rng.random() < 0.85 else 1,
            )
            for i, u in enumerate(users)
        )
        items, tags = [], []
        for p in profiles:
            bundle = PROFILES[rng.choice(list(PROFILES))]
            for _ in range(rng.randint(1, 3)):
                item = EvidenceItem(
                    institution=institution,
                    student=p,
                    source_type=SourceType.PROJECT,
                    title="Synthetic project",
                    verification_status=VerificationStatus.VERIFIED
                    if rng.random() < 0.5
                    else VerificationStatus.SELF_REPORTED,
                )
                items.append((item, rng.sample(bundle, k=min(3, len(bundle)))))
        EvidenceItem.objects.bulk_create([i for i, _ in items], batch_size=2000)
        for item, picked in items:
            for name, level in picked:
                tags.append(
                    EvidenceSkillTag(
                        institution=institution,
                        evidence=item,
                        skill=skill_pool[name],
                        claimed_level=max(1, min(4, level + rng.choice([-1, 0, 0, 1]))),
                    )
                )
        EvidenceSkillTag.objects.bulk_create(tags, batch_size=5000)
        made += n
    return made
