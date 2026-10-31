from django.dispatch import receiver

from apps.evidence.signals import evidence_changed
from apps.taxonomy.services import skill_merged

from .services import schedule_recompute


@receiver(evidence_changed)
def on_evidence_changed(sender, student, **kwargs):
    schedule_recompute(student.pk)


@receiver(skill_merged)
def on_skill_merged(sender, source, target, **kwargs):
    """Point evidence tags at the surviving skill, then rebuild affected profiles."""
    from apps.evidence.models import EvidenceSkillTag

    affected = set()
    for tag in EvidenceSkillTag.objects.filter(skill=source).select_related("evidence"):
        affected.add(tag.evidence.student_id)
        if EvidenceSkillTag.objects.filter(evidence_id=tag.evidence_id, skill=target).exists():
            tag.delete()
        else:
            tag.skill = target
            tag.save(update_fields=["skill", "updated_at"])
    for student_id in affected:
        schedule_recompute(student_id)
