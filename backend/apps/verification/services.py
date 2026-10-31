from django.db import transaction

from apps.accounts.roles import Role, has_role
from apps.core.services import record_audit
from apps.evidence import services as evidence_services
from apps.evidence.models import EvidenceItem, VerificationStatus
from apps.notifications.services import notify

from .models import Decision, Verification


class VerificationError(ValueError):
    pass


def can_verify(reviewer, evidence):
    """Faculty verify evidence of their own mentees only (P06 §6). A student can never verify,
    and nobody can verify their own evidence."""
    return (
        has_role(reviewer, Role.FACULTY)
        and evidence.student.user_id != reviewer.pk
        and evidence.student.mentor_id == reviewer.pk
        and evidence.institution_id == reviewer.institution_id
    )


def pending_for_reviewer(reviewer):
    return (
        EvidenceItem.objects.filter(
            institution_id=reviewer.institution_id,
            student__mentor=reviewer,
            verification_status=VerificationStatus.PENDING,
        )
        .select_related("student__user", "student__department")
        .prefetch_related("skill_tags__skill")
        .order_by("submitted_at")
    )


@transaction.atomic
def decide(*, evidence, reviewer, decision, comment="", request=None):
    if not can_verify(reviewer, evidence):
        raise VerificationError("You can only review evidence of students you mentor.")
    if evidence.verification_status != VerificationStatus.PENDING:
        raise VerificationError("Only evidence pending verification can be reviewed.")
    if decision not in Decision.values:
        raise VerificationError("Unknown decision.")
    if decision == Decision.REJECTED and not comment.strip():
        raise VerificationError("Give the student a reason when rejecting evidence.")
    record = Verification.objects.create(
        institution_id=evidence.institution_id,
        evidence=evidence,
        reviewer=reviewer,
        decision=decision,
        comment=comment,
    )
    evidence_services.set_status(evidence, decision)
    record_audit(
        actor=reviewer, action=f"evidence.{decision}", target=evidence, request=request, after={"comment": comment}
    )
    notify(
        evidence.student.user,
        kind="verification_completed",
        title=f"Evidence {Decision(decision).label.lower()}: {evidence.title}",
        body=comment,
        link="/student/evidence",
    )
    return record


def notify_verification_requested(evidence):
    mentor = evidence.student.mentor
    if mentor is not None:
        notify(
            mentor,
            kind="verification_requested",
            title=f"Verification requested: {evidence.title}",
            body=f"{evidence.student.name} asked you to verify this evidence.",
            link="/faculty/verification",
        )
