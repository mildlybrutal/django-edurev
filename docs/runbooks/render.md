# Deploying on Render

> Status: `render.yaml` and this runbook were written on 2026-11-06 and checked locally
> (`manage.py check --deploy` under prod settings, health-check behaviour under test). **They have
> not been run against a real Render account yet.** Expect to adjust names or values on the first
> deploy, and record anything that changes here.

The general release and rollback rules in [deployment.md](deployment.md) still apply.

## What gets created

| Render resource | From `render.yaml` | Plan in the file | Why that plan |
|---|---|---|---|
| `placement-backend` (web, Docker) | `backend/Dockerfile`, gunicorn | Starter | Pre-deploy migrations and Shell need a paid plan |
| `placement-worker` (background worker, Docker) | same image, `celery worker -B` | Starter | Background workers have no free plan. Beat runs inside it, so keep it at **one** instance |
| `placement-frontend` (web, Node 22) | `frontend/`, `npm run build` / `npm start` | Starter | The free plan sleeps after 15 idle minutes; switch to Free for a demo if a slow first load is fine |
| `placement-redis` (Key Value) | | Free | Cache, throttling and broker data are disposable |
| `placement-db` (PostgreSQL 16) | | Basic 256 MB | Free databases are deleted after 30 days |

Check current prices on Render before choosing; the plan names in the file can be changed in the
dashboard afterwards.

**File storage:** resumes and certificates are stored in the PostgreSQL database
(`FILE_STORAGE=database`, [ADR 0011](../adr/0011-file-storage-in-postgres.md)), so no bucket or
outside account is needed. Each file is at most 5 MB and adds about its own size to the database;
watch the database's disk usage in the Render dashboard and resize it, or switch to S3, if it
fills up.

## First deploy

1. Push the branch that contains `render.yaml` to GitHub (Render reads it from the repository).
2. Render dashboard → **New** → **Blueprint** → pick the repository. Render lists the resources
   above and asks for every `sync: false` value:

   | Service | Variable | Value |
   |---|---|---|
   | backend | `DJANGO_ALLOWED_HOSTS` | `placement-backend.onrender.com` (the backend's own host, no `https://`) |
   | backend | `CSRF_TRUSTED_ORIGINS` | `https://placement-frontend.onrender.com` (comma-separate a recruiter domain if you add one) |
   | backend, worker | `GITHUB_TOKEN` | optional; leave empty |
   | frontend | `BACKEND_URL` | `https://placement-backend.onrender.com` |

   If Render gives a service a different `.onrender.com` name (names are global), use that
   name everywhere above.
3. Wait for all services to go live. The backend runs `migrate` before each deploy.
4. **First-time setup**, from the backend's **Shell** tab:

   ```bash
   python manage.py createsuperuser
   ```

   Then, in Django admin (`https://placement-backend.onrender.com/admin/`), create the
   Institution and the staff users, and back in the Shell:

   ```bash
   python manage.py seed_taxonomy <institution_code>
   ```

   Django admin has no stylesheet on this setup (static files are not served); it still works.
   **Never** run `seed_demo` or `seed_synthetic_cohort` against a database holding real students.
   For a demo-only deployment, seed a separate demo database instead.
5. Sign in on `https://placement-frontend.onrender.com`. Officers, heads and admins must enrol MFA
   (TOTP) on first sign-in, as in production.

## Checks after the first deploy

- `https://placement-backend.onrender.com/ready` returns `{"status": "ok"}` (database and Redis).
- Sign-in works through the frontend. If you get a CSRF error, `CSRF_TRUSTED_ORIGINS` does not
  match the frontend URL exactly (scheme included, no trailing slash).
- Upload a resume and open it in the viewer. The link stops working after 5 minutes (403).
- Link a GitHub profile and confirm it syncs. That shows the worker is consuming tasks.
- Open **Recruiter Access** and check that the IP recorded for your own sign-in is your real
  address. `NUM_PROXIES=2` assumes browser → Render → Next.js → Render → Django; if the address
  is a Render-internal one, change `NUM_PROXIES` and redeploy. Throttling and the audit log both
  depend on it.

## Recruiter portal on its own host (P06 §16)

Add a custom domain such as `recruiters.example.edu` to `placement-frontend` and append
`https://recruiters.example.edu` to `CSRF_TRUSTED_ORIGINS`. Auth cookies are host-only, so the
recruiter host never shares cookies with the internal portal.

## Health checks

Render probes `GET /health` from inside its network over plain HTTP. `LivenessMiddleware`
(`apps/core/middleware.py`) answers that one path before host validation and the HTTPS redirect,
so the probe is not rejected. Every other path, including `/ready`, gets the normal checks.
