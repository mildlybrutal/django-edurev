"""Certificate files for certification evidence. They share the resumes' private bucket (under a
`certificates/` prefix) and are only reachable through short-lived signed URLs issued after the
same visibility check as the evidence itself. Uploads are not malware-scanned (docs/status.md)."""

import hashlib
import uuid

from django.conf import settings

from apps.students.resumes import ensure_bucket, resume_storage, signed_url

# Declared content types are not trusted: the type is decided by the file's magic bytes.
SIGNATURES = [
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
]
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}


class CertificateFileError(ValueError):
    pass


def validate_certificate(uploaded):
    """Returns (content_type, suffix, sha256)."""
    max_bytes = getattr(settings, "CERTIFICATE_MAX_BYTES", 5 * 1024 * 1024)
    if uploaded.size > max_bytes:
        raise CertificateFileError(f"Certificate must be {max_bytes // (1024 * 1024)} MB or smaller.")
    name = uploaded.name.lower()
    if not any(name.endswith(s) for s in ALLOWED_SUFFIXES):
        raise CertificateFileError("Upload the certificate as a PDF, PNG or JPEG file.")
    uploaded.seek(0)
    head = uploaded.read(16)
    uploaded.seek(0)
    match = next((sig for sig in SIGNATURES if head.startswith(sig[0])), None)
    if match is None:
        raise CertificateFileError("That file is not a valid PDF, PNG or JPEG.")
    _, content_type, suffix = match
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    return content_type, suffix, digest.hexdigest()


def save_certificate(evidence, uploaded, suffix):
    ensure_bucket()
    key = f"certificates/{evidence.institution_id}/{evidence.student_id}/{uuid.uuid4().hex}{suffix}"
    return resume_storage().save(key, uploaded)


def certificate_url(evidence_file):
    return signed_url(evidence_file.file.name, content_type=evidence_file.content_type)
