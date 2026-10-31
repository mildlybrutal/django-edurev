# Backup and restore

> Status: verified locally on 2026-10-21. A `pg_dump` of the development database (3 MB) was restored into an empty scratch database, and row counts matched for the tables checked (students, drives, recruiter access log). No production backup schedule exists yet.

## What to back up

| Data | Where | Back up? |
|---|---|---|
| All domain data, users, audit and access logs | PostgreSQL | **Yes**, daily, retained per the institution's retention policy (CES: 7 years for academic records) |
| Cache, throttles, lockouts, Celery queue | Redis | No. It is rebuilt automatically, and queued jobs can be re-run |
| Uploaded files | None yet (evidence is links/text) | n/a |

## Daily backup (managed PostgreSQL)

Prefer the provider's automated daily snapshots plus point-in-time recovery. For a logical backup:

```bash
pg_dump --format=custom --no-owner --file=placement-$(date +%F).dump "$DATABASE_URL"
```

Store dumps encrypted, off-site, with a retention policy. They contain personal data.

## Restore

1. Stop the web, worker and beat processes, so nothing writes during the restore.
2. Create an empty database, then restore:
   ```bash
   pg_restore --no-owner --clean --if-exists --dbname="$DATABASE_URL" placement-YYYY-MM-DD.dump
   ```
3. Run `python manage.py migrate` (a no-op if the dump came from the same release).
4. Start the processes, check that `/ready` returns 200, then sign in and spot-check a student profile, a drive and the recruiter access log.
5. Run the batch-readiness job (**Placement → Batch Analytics**) to rebuild derived results, if wanted.

## Local verification (docker compose)

```bash
docker compose exec -T db pg_dump -U placement -Fc placement > placement.dump
docker compose exec -T db psql -U placement -c "CREATE DATABASE restore_check;"
docker compose exec -T db pg_restore -U placement --no-owner -d restore_check < placement.dump
docker compose exec -T db psql -U placement -d restore_check -tAc \
  "select count(*) from students_studentprofile"   # compare with the live database
docker compose exec -T db psql -U placement -c "DROP DATABASE restore_check;"
```
