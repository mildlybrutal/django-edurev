from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Institution(TimeStampedModel):
    """Tenant root. Every domain record carries an institution (CES §1.2)."""

    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    allow_student_signup = models.BooleanField(default=False, help_text="Students may create their own accounts.")
    student_email_domain = models.CharField(
        max_length=120, blank=True, help_text="If set, self sign-up requires an email at this domain (e.g. univ.edu)."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantModel(TimeStampedModel):
    """Base for every institution-scoped domain model."""

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True


class ImmutableRecordError(Exception):
    pass


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableRecordError(f"{self.model.__name__} rows are append-only.")

    def delete(self):
        raise ImmutableRecordError(f"{self.model.__name__} rows are append-only.")


class AppendOnlyModel(models.Model):
    """Rows can be inserted but never updated or deleted through the ORM."""

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError(f"{type(self).__name__} rows are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError(f"{type(self).__name__} rows are append-only.")


class AuditLog(AppendOnlyModel):
    """Immutable record of a privileged action (CES §1.4). Stores IDs, never personal data."""

    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.action} by {self.actor_id} at {self.created_at:%Y-%m-%d %H:%M}"


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class BackgroundJob(models.Model):
    """Progress record for long-running Celery work (batch readiness, drive matching)."""

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED)
    params = models.JSONField(default=dict, blank=True)
    total = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.status}"

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class StoredFile(models.Model):
    """Bytes of an uploaded file (resume, certificate) when FILE_STORAGE is "database"
    (apps.core.file_storage.DatabaseStorage, ADR 0011). Access control lives on the records that
    reference a file by name (StudentResume, EvidenceFile); files are only ever reached through a
    short-lived signed link issued after their permission check."""

    name = models.CharField(max_length=300, unique=True)
    content = models.BinaryField()
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
