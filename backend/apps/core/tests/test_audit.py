import pytest

from apps.core.models import AuditLog, ImmutableRecordError
from apps.core.services import record_audit

pytestmark = pytest.mark.django_db


def test_record_audit_captures_actor_target_and_institution(student):
    entry = record_audit(actor=student, action="test.action", target=student, after={"x": 1})
    assert entry.actor == student
    assert entry.institution == student.institution
    assert (entry.target_type, entry.target_id) == ("accounts.User", str(student.pk))


def test_audit_entries_cannot_be_updated_or_deleted(student):
    entry = record_audit(actor=student, action="test.action")
    entry.action = "tampered"
    with pytest.raises(ImmutableRecordError):
        entry.save()
    with pytest.raises(ImmutableRecordError):
        entry.delete()
    with pytest.raises(ImmutableRecordError):
        AuditLog.objects.filter(pk=entry.pk).update(action="tampered")
    with pytest.raises(ImmutableRecordError):
        AuditLog.objects.all().delete()
