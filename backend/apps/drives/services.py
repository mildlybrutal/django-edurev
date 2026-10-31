from django.db import transaction
from django.utils import timezone

from apps.core.services import record_audit
from apps.notifications.services import notify
from apps.taxonomy.models import Level

from . import eligibility as eligibility_rules
from .models import (
    ACTIVE_REGISTRATION,
    Drive,
    DriveRequirement,
    DriveStatus,
    EligibilityResult,
    EligibilityRule,
    JDStatus,
    Registration,
    RegistrationStatus,
    RequirementSource,
)


class DriveError(ValueError):
    pass


EDITABLE_STATUSES = (DriveStatus.DRAFT, DriveStatus.PUBLISHED)


def _require_editable(drive):
    if drive.status not in EDITABLE_STATUSES:
        raise DriveError("Requirements and eligibility can only change while the drive is draft or open.")


@transaction.atomic
def create_drive(*, institution, company, role_title, created_by, request=None, **fields):
    if company.institution_id != institution.id:
        raise DriveError("Company belongs to another institution.")
    target_role = fields.get("target_role")
    if target_role is not None and target_role.institution_id != institution.id:
        raise DriveError("Target role belongs to another institution.")
    _check_dates(fields.get("registration_opens_at"), fields.get("registration_closes_at"))
    drive = Drive.objects.create(
        institution=institution, company=company, role_title=role_title, created_by=created_by, **fields
    )
    if target_role is not None:
        apply_role_template(drive, target_role)
    record_audit(actor=created_by, action="drive.create", target=drive, request=request)
    return drive


def _check_dates(opens, closes):
    if opens and closes and closes <= opens:
        raise DriveError("Registration must close after it opens.")


def update_drive(drive, *, actor, request=None, **fields):
    if drive.status in (DriveStatus.COMPLETED, DriveStatus.CANCELLED):
        raise DriveError("Completed or cancelled drives cannot be edited.")
    for name, value in fields.items():
        setattr(drive, name, value)
    _check_dates(drive.registration_opens_at, drive.registration_closes_at)
    drive.save()
    record_audit(actor=actor, action="drive.update", target=drive, request=request, after={"fields": sorted(fields)})
    return drive


def apply_role_template(drive, role):
    """Seed requirements from a taxonomy target role (only skills not already required)."""
    _require_editable(drive)
    existing = set(drive.requirements.values_list("skill_id", flat=True))
    DriveRequirement.objects.bulk_create(
        DriveRequirement(
            institution_id=drive.institution_id,
            drive=drive,
            skill_id=rs.skill_id,
            required_level=rs.required_level,
            weight=rs.weight,
            is_mandatory=rs.is_core,
            source=RequirementSource.ROLE_TEMPLATE,
        )
        for rs in role.role_skills.all()
        if rs.skill_id not in existing
    )


def set_requirement(drive, *, skill, required_level, weight, is_mandatory, source=RequirementSource.MANUAL):
    _require_editable(drive)
    if skill.institution_id != drive.institution_id or not skill.is_active:
        raise DriveError("Unknown skill.")
    if required_level not in Level.values or required_level == Level.NONE:
        raise DriveError("Required level must be Beginner to Expert.")
    if weight < 1 or weight > 10:
        raise DriveError("Weight must be between 1 and 10.")
    requirement, _ = DriveRequirement.objects.update_or_create(
        drive=drive,
        skill=skill,
        defaults={
            "institution_id": drive.institution_id,
            "required_level": required_level,
            "weight": weight,
            "is_mandatory": is_mandatory,
            "source": source,
        },
    )
    return requirement


def remove_requirement(drive, skill_id):
    _require_editable(drive)
    DriveRequirement.objects.filter(drive=drive, skill_id=skill_id).delete()


def set_eligibility_rule(drive, rule_type, value):
    _require_editable(drive)
    try:
        value = eligibility_rules.validate_rule_value(rule_type, value)
    except eligibility_rules.RuleValueError as exc:
        raise DriveError(str(exc)) from exc
    rule, _ = EligibilityRule.objects.update_or_create(
        drive=drive, rule_type=rule_type, defaults={"institution_id": drive.institution_id, "value": value}
    )
    return rule


def remove_eligibility_rule(drive, rule_type):
    _require_editable(drive)
    EligibilityRule.objects.filter(drive=drive, rule_type=rule_type).delete()


# --- JD processing -----------------------------------------------------------------------


def submit_jd(drive, text):
    _require_editable(drive)
    if not text.strip():
        raise DriveError("Paste the job description text.")
    drive.job_description = text
    drive.jd_status = JDStatus.PROCESSING
    drive.jd_extraction = {}
    drive.save(update_fields=["job_description", "jd_status", "jd_extraction", "updated_at"])
    from .tasks import process_jd_task

    transaction.on_commit(lambda: process_jd_task.delay(drive.pk))
    return drive


def run_jd_processing(drive):
    from .jd import process_jd

    try:
        drive.jd_extraction = process_jd(drive.job_description, drive.institution_id)
        drive.jd_status = JDStatus.READY
    except Exception:
        drive.jd_status = JDStatus.FAILED
        raise
    finally:
        drive.save(update_fields=["jd_extraction", "jd_status", "updated_at"])
    return drive


@transaction.atomic
def apply_jd_extraction(drive, *, skills, rules, actor, request=None):
    """Officer-confirmed subset of the extraction: `skills` is a list of
    {skill_id, required_level, weight, is_mandatory}; `rules` a list of {rule_type, value}."""
    from apps.taxonomy.models import Skill

    _require_editable(drive)
    if drive.jd_status not in (JDStatus.READY, JDStatus.APPLIED):
        raise DriveError("The JD has not been processed yet.")
    for item in skills:
        skill = Skill.objects.filter(pk=item["skill_id"], institution_id=drive.institution_id).first()
        if skill is None:
            raise DriveError("Unknown skill.")
        set_requirement(
            drive,
            skill=skill,
            required_level=item["required_level"],
            weight=item["weight"],
            is_mandatory=item["is_mandatory"],
            source=RequirementSource.JD,
        )
    for rule in rules:
        set_eligibility_rule(drive, rule["rule_type"], rule["value"])
    drive.jd_status = JDStatus.APPLIED
    drive.save(update_fields=["jd_status", "updated_at"])
    record_audit(
        actor=actor,
        action="drive.jd.apply",
        target=drive,
        request=request,
        after={"skills": len(skills), "rules": len(rules)},
    )
    return drive


# --- lifecycle -----------------------------------------------------------------------------

TRANSITIONS = {
    DriveStatus.DRAFT: {DriveStatus.PUBLISHED, DriveStatus.CANCELLED},
    DriveStatus.PUBLISHED: {DriveStatus.REGISTRATION_CLOSED, DriveStatus.CANCELLED},
    DriveStatus.REGISTRATION_CLOSED: {DriveStatus.SHORTLISTING, DriveStatus.CANCELLED},
    DriveStatus.SHORTLISTING: {DriveStatus.COMPLETED, DriveStatus.CANCELLED},
    DriveStatus.COMPLETED: set(),
    DriveStatus.CANCELLED: set(),
}


@transaction.atomic
def transition(drive, new_status, *, actor, request=None):
    if new_status not in TRANSITIONS[drive.status]:
        raise DriveError(f"Cannot move a {drive.get_status_display().lower()} drive to {new_status}.")
    if new_status == DriveStatus.PUBLISHED and not drive.requirements.exists():
        raise DriveError("Add at least one skill requirement before publishing.")
    before = drive.status
    drive.status = new_status
    drive.save(update_fields=["status", "updated_at"])
    record_audit(
        actor=actor,
        action="drive.status",
        target=drive,
        request=request,
        before={"status": before},
        after={"status": new_status},
    )
    if new_status == DriveStatus.PUBLISHED:
        from apps.matching.tasks import run_drive_matching_task

        transaction.on_commit(lambda: run_drive_matching_task.delay(drive.pk, notify_students=True))
    return drive


def evaluate_and_store(drive, students):
    """Evaluate eligibility for many students and upsert EligibilityResult rows."""
    rules = list(drive.eligibility_rules.all())
    results = {}
    rows = []
    for student in students:
        ok, reasons = eligibility_rules.evaluate(student, rules)
        results[student.pk] = (ok, reasons)
        rows.append(
            EligibilityResult(
                institution_id=drive.institution_id, drive=drive, student=student, is_eligible=ok, reasons=reasons
            )
        )
    EligibilityResult.objects.bulk_create(
        rows,
        batch_size=1000,
        update_conflicts=True,
        unique_fields=["drive", "student"],
        update_fields=["is_eligible", "reasons", "computed_at"],
    )
    return results


def registration_open(drive, now=None):
    now = now or timezone.now()
    if drive.status != DriveStatus.PUBLISHED:
        return False
    if drive.registration_opens_at and now < drive.registration_opens_at:
        return False
    return not (drive.registration_closes_at and now > drive.registration_closes_at)


@transaction.atomic
def register(drive, student):
    if drive.institution_id != student.institution_id:
        raise DriveError("Drive not found.")
    if not registration_open(drive):
        raise DriveError("Registration for this drive is not open.")
    ok, reasons = evaluate_and_store(drive, [student])[student.pk]
    if not ok:
        missed = "; ".join(r["message"] for r in reasons if not r["passed"])
        raise DriveError(f"You are not eligible: {missed}.")
    registration, created = Registration.objects.get_or_create(
        drive=drive, student=student, defaults={"institution_id": drive.institution_id}
    )
    if not created:
        if registration.status != RegistrationStatus.WITHDRAWN:
            raise DriveError("You are already registered.")
        registration.status = RegistrationStatus.REGISTERED
        registration.save(update_fields=["status", "updated_at"])
    return registration


def withdraw(drive, student):
    registration = Registration.objects.filter(drive=drive, student=student).first()
    if registration is None or registration.status != RegistrationStatus.REGISTERED:
        raise DriveError("You can only withdraw an active registration before shortlisting.")
    if not registration_open(drive):
        raise DriveError("Registration has closed; contact the placement cell.")
    registration.status = RegistrationStatus.WITHDRAWN
    registration.save(update_fields=["status", "updated_at"])
    return registration


OFFICER_DECISIONS = {
    RegistrationStatus.SHORTLISTED,
    RegistrationStatus.NOT_SHORTLISTED,
    RegistrationStatus.SELECTED,
    RegistrationStatus.NOT_SELECTED,
}


@transaction.atomic
def decide_registration(registration, status, *, actor, request=None):
    drive = registration.drive
    if status not in OFFICER_DECISIONS:
        raise DriveError("Unknown decision.")
    if registration.status == RegistrationStatus.WITHDRAWN:
        raise DriveError("The student has withdrawn.")
    if drive.status not in (DriveStatus.REGISTRATION_CLOSED, DriveStatus.SHORTLISTING):
        raise DriveError("Close registration before shortlisting.")
    if status in (RegistrationStatus.SELECTED, RegistrationStatus.NOT_SELECTED) and registration.status not in (
        RegistrationStatus.SHORTLISTED,
        RegistrationStatus.SELECTED,
        RegistrationStatus.NOT_SELECTED,
    ):
        raise DriveError("Only shortlisted students can be selected.")
    before = registration.status
    registration.status = status
    registration.save(update_fields=["status", "updated_at"])
    record_audit(
        actor=actor,
        action="registration.decide",
        target=registration,
        request=request,
        before={"status": before},
        after={"status": status},
    )
    notify(
        registration.student.user,
        kind="shortlist_result",
        title=f"{drive}: {RegistrationStatus(status).label}",
        link=f"/student/drives/{drive.pk}",
    )
    return registration


def active_registrations(drive):
    return Registration.objects.filter(drive=drive, status__in=ACTIVE_REGISTRATION)
