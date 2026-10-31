# Deployment and rollback runbook

> Status: written for the intended production shape. **It has not been exercised against a real environment yet** (see [status.md](../status.md)).

## Components

| Process | Command | Notes |
|---|---|---|
| web | `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3` (image default) | `DJANGO_SETTINGS_MODULE=config.settings.prod` |
| worker | `celery -A config worker --loglevel=INFO` | Same image. Scale for batch jobs |
| beat | `celery -A config beat --loglevel=INFO` | Exactly **one** instance (checkpoint reminders) |
| frontend | `npm ci && npm run build && npm start` | `BACKEND_URL` unused behind a proxy that routes `/api/` |
| PostgreSQL 16 | managed | Daily backups (see [backup-restore.md](backup-restore.md)) |
| Redis 7 | managed | Cache, throttling, lockout and Celery broker. Data is disposable |

**Reverse proxy:** route `/api/`, `/admin/`, `/health` and `/ready` to Django, and everything else to Next.js. Serve the recruiter portal from its own host (e.g. `recruiters.example.edu`) so its cookies never share a domain with the internal portal (P06 §16). Leave `AUTH_COOKIE_DOMAIN` unset (host-only cookies).

## Required production configuration

- **Secrets:** `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY`, distinct and long random values, from the secret store.
- **Datastores:** `DATABASE_URL` and `REDIS_URL`.
- **Hosts and origins:** `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, set to the public origins of both portals.
- **Proxies:** set `NUM_PROXIES` to the number of trusted proxies, so throttling and the audit log record the client IP.
- **Email:** `EMAIL_BACKEND` plus Django SMTP settings, and `DEFAULT_FROM_EMAIL`.
- **MFA:** keep the default `MFA_REQUIRED_ROLES`, so admin, placement head and officer must use MFA.
- **Not demo data:** never run `seed_demo` or `seed_synthetic_cohort` against production.

## Release procedure

1. Check that CI is green on `main`: lint, tests, schema, audits and e2e.
2. Build and tag images, e.g. `backend:<git-sha>`.
3. **Back up the database** (see the backup runbook).
4. Run migrations once: `python manage.py migrate --noinput`. Migrations are forward-compatible with the previous release wherever possible.
5. Run `python manage.py collectstatic --noinput` if the admin is served by Django.
6. Roll the web, then worker, then beat processes, then the frontend.
7. Smoke test:
   - `GET /ready` returns 200.
   - Sign in as a test officer, open the dashboard and run "Run matching" on a test drive.
   - Recruiter sign-in on the recruiter host.
8. Watch the error logs (JSON on stdout) and job failures (`BackgroundJob.status = failed`) for 30 minutes.

## Rollback

- **Application only** (no new migrations, or only additive ones): redeploy the previous image tags.
- **Migration problem:** stop the worker and beat, then run `python manage.py migrate <app> <previous_migration>` for each app changed in the release. All migrations are reversible except data loss from dropped columns, which the release must avoid. Then redeploy the previous images.
- **Data corruption:** restore the pre-release backup (backup runbook) and redeploy the previous images.

## First-time setup

```bash
python manage.py migrate
python manage.py createsuperuser          # platform admin for Django admin
# In Django admin: create the Institution, then users with roles (groups) and institution set.
python manage.py seed_taxonomy <institution_code>   # starter taxonomy (editable afterwards)
```
