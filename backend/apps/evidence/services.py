from django.db import transaction

from apps.taxonomy.models import Level

from .models import INSTITUTIONAL_SOURCES, EvidenceItem, EvidenceSkillTag, SourceType, VerificationStatus
from .signals import evidence_changed


class EvidenceError(ValueError):
    pass


def _validate_tags(student, tags):
    seen = set()
    for skill, level in tags:
        if skill.institution_id != student.institution_id or not skill.is_active:
            raise EvidenceError("Unknown skill.")
        if skill.pk in seen:
            raise EvidenceError(f"{skill.name} is tagged twice.")
        if level not in Level.values or level == Level.NONE:
            raise EvidenceError("Claimed level must be Beginner to Expert.")
        seen.add(skill.pk)


def _set_tags(evidence, tags):
    evidence.skill_tags.all().delete()
    EvidenceSkillTag.objects.bulk_create(
        EvidenceSkillTag(institution_id=evidence.institution_id, evidence=evidence, skill=skill, claimed_level=level)
        for skill, level in tags
    )


@transaction.atomic
def submit_evidence(
    *,
    student,
    source_type,
    title,
    description="",
    source_url="",
    external_reference="",
    extracted_data=None,
    tags=(),
    request_verification=False,
):
    """Student-submitted evidence. Institutional sources cannot be self-submitted."""
    if source_type in INSTITUTIONAL_SOURCES:
        raise EvidenceError("This evidence type is recorded by the institution, not by students.")
    if source_type not in SourceType.values:
        raise EvidenceError("Unknown source type.")
    _validate_tags(student, tags)
    item = EvidenceItem.objects.create(
        institution_id=student.institution_id,
        student=student,
        source_type=source_type,
        title=title,
        description=description,
        source_url=source_url,
        external_reference=external_reference,
        extracted_data=extracted_data or {},
        verification_status=VerificationStatus.PENDING if request_verification else VerificationStatus.SELF_REPORTED,
        recorded_by=student.user,
    )
    _set_tags(item, tags)
    _changed(item, created=True)
    return item


@transaction.atomic
def record_institutional_evidence(
    *, student, source_type, title, recorded_by, description="", tags=(), extracted_data=None
):
    """Evidence from institutional records (academics, assessments, mock interviews). Recorded by
    staff, so it is verified on creation; the recorder is kept as provenance."""
    if source_type not in INSTITUTIONAL_SOURCES:
        raise EvidenceError("Only institutional evidence types can be recorded this way.")
    _validate_tags(student, tags)
    item = EvidenceItem.objects.create(
        institution_id=student.institution_id,
        student=student,
        source_type=source_type,
        title=title,
        description=description,
        extracted_data=extracted_data or {},
        verification_status=VerificationStatus.VERIFIED,
        recorded_by=recorded_by,
    )
    _set_tags(item, tags)
    _changed(item, created=True)
    return item


EDITABLE_STATUSES = {VerificationStatus.SELF_REPORTED, VerificationStatus.REJECTED}


@transaction.atomic
def update_evidence(item, *, tags=None, **fields):
    """Students may edit only unverified, unreviewed items. Editing a rejected item returns it
    to self-reported so it can be resubmitted."""
    if item.source_type in INSTITUTIONAL_SOURCES:
        raise EvidenceError("Institutional evidence cannot be edited.")
    if item.verification_status not in EDITABLE_STATUSES:
        raise EvidenceError("Evidence that is pending or verified cannot be edited.")
    for name in ("title", "description", "source_url", "external_reference", "extracted_data"):
        if name in fields:
            setattr(item, name, fields[name])
    item.verification_status = VerificationStatus.SELF_REPORTED
    item.save()
    if tags is not None:
        _validate_tags(item.student, tags)
        _set_tags(item, tags)
    _changed(item)
    return item


def delete_evidence(item):
    if item.source_type in INSTITUTIONAL_SOURCES:
        raise EvidenceError("Institutional evidence cannot be deleted.")
    if item.verification_status == VerificationStatus.VERIFIED:
        raise EvidenceError("Verified evidence cannot be deleted.")
    student = item.student
    item.delete()
    evidence_changed.send(sender=EvidenceItem, student=student, evidence=None)


def request_verification(item):
    if item.verification_status != VerificationStatus.SELF_REPORTED:
        raise EvidenceError("Only self-reported evidence can be sent for verification.")
    if not item.skill_tags.exists():
        raise EvidenceError("Tag at least one skill before requesting verification.")
    item.verification_status = VerificationStatus.PENDING
    item.save(update_fields=["verification_status", "updated_at"])
    _changed(item)
    return item


@transaction.atomic
def refresh_synced_evidence(item, *, title, source_url, extracted_data, tags):
    """Update evidence that an integration re-synced (GitHub, LeetCode). A verified item stays
    verified (verification attests the account is the student's); a rejected one returns to
    self-reported because its data changed."""
    _validate_tags(item.student, tags)
    item.title, item.source_url, item.extracted_data = title, source_url, extracted_data
    if item.verification_status == VerificationStatus.REJECTED:
        item.verification_status = VerificationStatus.SELF_REPORTED
    item.save()
    _set_tags(item, tags)
    _changed(item)
    return item


def set_status(item, status):
    """Used only by the verification module."""
    item.verification_status = status
    item.save(update_fields=["verification_status", "updated_at"])
    _changed(item)


def _changed(item, created=False):
    transaction.on_commit(
        lambda: evidence_changed.send(sender=EvidenceItem, student=item.student, evidence=item, created=created)
    )
