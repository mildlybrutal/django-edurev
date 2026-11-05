"""Resume storage. Files live in S3-compatible object storage (CES §1.1: never MEDIA_ROOT on the
app server) under a private bucket, and are viewed only through short-lived signed URLs issued
after an authorization check. Tests use Django's in-memory storage."""

import hashlib
import uuid

from django.conf import settings
from django.core.files.storage import storages

PDF_MAGIC = b"%PDF-"


class ResumeError(ValueError):
    pass


def resume_storage():
    return storages["resumes"]


def object_key(student, original_name):
    return f"resumes/{student.institution_id}/{student.pk}/{uuid.uuid4().hex}.pdf"


def validate_pdf(uploaded):
    """Size cap, .pdf name and the PDF magic bytes. The declared content type is not trusted."""
    max_bytes = getattr(settings, "RESUME_MAX_BYTES", 5 * 1024 * 1024)
    if uploaded.size > max_bytes:
        raise ResumeError(f"Resume must be {max_bytes // (1024 * 1024)} MB or smaller.")
    if uploaded.size < len(PDF_MAGIC) or not uploaded.name.lower().endswith(".pdf"):
        raise ResumeError("Upload your resume as a PDF file.")
    uploaded.seek(0)
    head = uploaded.read(1024)
    uploaded.seek(0)
    if not head.lstrip().startswith(PDF_MAGIC):
        raise ResumeError("That file is not a valid PDF.")
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    return digest.hexdigest()


def ensure_bucket():
    """Create the private bucket on first use (S3 backends only)."""
    storage = resume_storage()
    if not hasattr(storage, "bucket_name") or getattr(ensure_bucket, "_done", False):
        return
    client = storage.connection.meta.client
    try:
        client.head_bucket(Bucket=storage.bucket_name)
    except Exception:
        client.create_bucket(Bucket=storage.bucket_name)
    ensure_bucket._done = True


def signed_url(name, expires=None, content_type="application/pdf"):
    """A time-limited URL the browser can open. For S3 backends the URL is signed against the
    public endpoint (the browser cannot reach the in-cluster hostname)."""
    expires = expires or getattr(settings, "RESUME_URL_EXPIRY_SECONDS", 300)
    storage = resume_storage()
    if hasattr(storage, "bucket_name"):
        from storages.backends.s3 import S3Storage

        public = getattr(settings, "RESUME_S3_PUBLIC_URL", "") or None
        options = {**settings.STORAGES["resumes"].get("OPTIONS", {})}
        if public:
            options["endpoint_url"] = public
        return S3Storage(**options).url(
            name,
            expire=expires,
            parameters={
                "ResponseContentType": content_type,
                "ResponseContentDisposition": "inline",
            },
        )
    return storage.url(name)
