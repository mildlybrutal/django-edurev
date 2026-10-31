# ADR 0010: Resume object storage and coding-activity sync

**Status:** accepted (2026-10-21)

## Context

The project owner asked for three things:
- resume upload and viewing;
- GitHub and LeetCode activity, fetched and rated "for better evaluation";
- student self sign-up with a first-run pop-up for those links.

CES §1.1 forbids keeping uploads on the app server's disk. AGENTS.md §3 says external activity is evidence, not proof of expertise.

## Decisions

1. **Resumes go in S3-compatible object storage** through `django-storages[s3]` and `boto3`. Those are the only new backend dependencies; both are needed for S3 storage and signed URLs.
   - The bucket is private. Files are viewed only through 5-minute signed links, issued after the same object-level check as the rest of the student API.
   - Every view by staff is audited; every view by a recruiter is access-logged.
   - Uploads are PDF only, up to 5 MB, with the magic bytes checked. The last 3 versions are kept.
2. **Local and CI storage is SeaweedFS (`chrislusf/seaweedfs:4.48`), not MinIO.** The project owner chose MinIO, but its images could no longer be pulled publicly (Docker Hub said "repository does not exist"; quay.io returned 401). SeaweedFS speaks the S3 API, including the signed URLs we need. The application code depends only on S3, so production can use AWS S3, R2 or MinIO without code changes.
3. **GitHub and LeetCode are fetched server-side on Celery, using only the standard library.**
   - Only two fixed hosts are contacted, and students supply a validated username, never a URL, so there is no SSRF surface.
   - GitHub uses the official REST API. LeetCode uses its **unofficial** public GraphQL endpoint, which the project owner chose knowing it may break; the UI labels it as unofficial.
4. **Coding activity is a fifth readiness dimension** (default weight 10, configurable), at the project owner's request. Each synced profile is also one unverified evidence item, capped by the evidence rules. The rating formula is in `docs/scoring-policy.md` §9. It is an implementation choice, not part of the P06 specification.
5. **Self sign-up is opt-in per institution** (`allow_student_signup`), with an optional email domain. CGPA and backlogs entered at sign-up are flagged `academic_record_verified = false` until the placement cell confirms them, and the UI says so wherever eligibility is shown.

## Consequences

- There is a new compose service (`objectstore`) and new environment variables (see `docs/env.md`).
- If LeetCode changes its endpoint, its ratings stop updating. The last good rating is kept and the error is shown.
- Uploaded files are not scanned for malware. This is a known gap in `docs/status.md`.
