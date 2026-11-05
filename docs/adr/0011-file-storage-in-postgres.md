# ADR 0011: Store uploaded files in PostgreSQL by default

**Status:** accepted (2026-11-06). Changes the default storage from [ADR 0010](0010-resume-object-storage-and-coding-sync.md) §1; S3 stays supported.

## Context

Resumes (PDF) and certificate files (PDF, PNG or JPEG) are capped at 5 MB each. ADR 0010 stored
them in S3-compatible object storage. The target host, Render, has no object storage, and the
project owner has no free S3-compatible service available. CES §1.1 forbids keeping uploads on
the app server's disk, which rules out a persistent disk attached to the web service.

## Decision

1. **`FILE_STORAGE=database` is the default.** `apps.core.file_storage.DatabaseStorage` keeps each
   file's bytes in a `StoredFile` row (PostgreSQL `bytea`). The resume and certificate models,
   their upload validation and their permission checks are unchanged: they only use Django's
   storage API.
2. **Files are reached only through signed, expiring links.** `signed_url` returns
   `/api/v1/files/<token>/`. The token is signed with the Django secret key and carries the file
   name, its content type (decided from magic bytes at upload) and an absolute expiry (5 minutes,
   `RESUME_URL_EXPIRY_SECONDS`). This is the same model as an S3 pre-signed URL: the link is issued
   only after the object-level permission check and audit entry, and the link itself is the
   authorization when opened. A tampered or expired link returns 403.
3. **Responses are sandboxed.** Files are served from the app's own origin, so the view sends
   `Content-Security-Policy: sandbox`, `X-Content-Type-Options: nosniff`,
   `Cache-Control: private, no-store` and `X-Frame-Options: SAMEORIGIN` (the in-app viewer is an
   iframe; Django's default `DENY` would block it). Opening links is throttled per IP
   (`THROTTLE_FILE_LINK`).
4. **`FILE_STORAGE=s3` restores ADR 0010's behaviour**, using the existing `RESUME_S3_*` settings.

## Consequences

- No outside storage account is needed, locally, in CI or on Render.
- **CES §1.1 still holds:** files are in the database, not on the app server's disk.
- The database grows by about the size of each upload. At 5 MB per file this suits a demo or a
  single institution's resumes; at larger scale, or if backups become slow, switch to S3.
- Files are included in database backups automatically, which is simpler than backing up a
  bucket separately.
- Switching backends does not migrate existing files. Moving from one to the other needs a copy
  script, which is not written.
- The token is signed, not encrypted: the file name inside it is readable. Names contain only
  institution and record ids plus a random uuid, as S3 object keys did.
