# Environment variable reference

All configuration is by environment variable (CES §1.2). Local defaults live in `.env.example`; copy it to `.env`.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | yes | — | Django signing key. Generate a long random value per environment |
| `DJANGO_DEBUG` | no | `false` (`true` in dev settings) | Debug mode. Never true in production |
| `DJANGO_ALLOWED_HOSTS` | prod | dev: `localhost,127.0.0.1,backend` | Comma-separated host names |
| `DJANGO_SETTINGS_MODULE` | no | `config.settings.dev` | `config.settings.{dev,test,prod}` |
| `DATABASE_URL` | yes | — | PostgreSQL 16 URL, e.g. `postgres://user:pass@db:5432/placement` |
| `DATABASE_CONN_MAX_AGE` | no | `60` | Persistent connection lifetime (seconds) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | compose | — | Used by the `db` container in docker-compose |
| `REDIS_URL` | yes | — | Django cache (throttling, lockout, debounce) |
| `CELERY_BROKER_URL` | no | `REDIS_URL` | Celery broker |
| `CELERY_RESULT_BACKEND` | no | `REDIS_URL` | Celery results |
| `JWT_SIGNING_KEY` | no | `DJANGO_SECRET_KEY` | Signs access/refresh tokens. Set separately in production |
| `JWT_ACCESS_MINUTES` | no | `10` | Access token lifetime |
| `JWT_REFRESH_HOURS` | no | `24` | Refresh token lifetime (rotated on every use) |
| `AUTH_COOKIE_SECURE` | no | `true` (`false` in dev settings) | `Secure` flag on auth cookies |
| `AUTH_COOKIE_DOMAIN` | no | unset (host-only) | Cookie domain. Leave host-only so the recruiter host never shares cookies (P06 §16) |
| `CSRF_TRUSTED_ORIGINS` | prod | `[]` (dev: `http://localhost:3000,http://127.0.0.1:3000`) | Origins of the frontend allowed to make unsafe requests, e.g. `https://placement.example.edu`. Needed because the browser's `Origin` is the Next.js host, not Django's |
| `NUM_PROXIES` | prod | `0` | Number of trusted reverse proxies, used for client IP in throttling |
| `THROTTLE_ANON` / `THROTTLE_USER` | no | `60/min` / `600/min` | Default DRF throttle rates |
| `THROTTLE_LOGIN` / `THROTTLE_TOKEN_REFRESH` | no | `10/min` / `30/min` | Per-IP rates for auth endpoints |
| `LOGIN_LOCKOUT_THRESHOLD` | no | `5` | Failed logins per email before lockout |
| `LOGIN_LOCKOUT_SECONDS` | no | `900` | Lockout window |
| `DJANGO_SECURE_SSL_REDIRECT` | no | `true` (prod) | Redirect http to https |
| `DJANGO_SECURE_HSTS_SECONDS` | no | `31536000` (prod) | HSTS max-age |
| `THROTTLE_RECRUITER` / `THROTTLE_RECRUITER_LOGIN` | no | `30/min` / `5/min` | Recruiter-portal throttle scopes (separate from internal ones, P06 §16) |
| `MFA_REQUIRED_ROLES` | no | `admin,placement_head,placement_officer` (dev: empty) | Roles that must enrol TOTP; until they do, their session can only reach `/auth/*` |
| `PROFILE_RECOMPUTE_DEBOUNCE_SECONDS` | no | `30` (dev: `5`) | Debounce window for skill-profile and readiness recompute after evidence changes |
| `NOTIFICATION_EMAIL_KINDS` | no | `verification_completed,shortlist_result,checkpoint_due` | Notification kinds also sent by email (all are always in-app) |
| `EMAIL_BACKEND` | no | console backend | Django email backend; set SMTP settings for real delivery |
| `DEFAULT_FROM_EMAIL` | no | `placement@localhost` | Sender address |
| `LOG_LEVEL` | no | `INFO` | Root log level (JSON output) |
| `THROTTLE_SIGNUP` | no | `5/min` | Per-IP rate for student self sign-up |
| `RESUME_S3_ACCESS_KEY` / `RESUME_S3_SECRET_KEY` | yes (compose) | — | Credentials for resume object storage. In compose they also configure the SeaweedFS S3 gateway. Generate your own; never commit them |
| `RESUME_S3_BUCKET` | no | `resumes` | Private bucket, created on first upload |
| `RESUME_S3_ENDPOINT_URL` | no | `http://localhost:8333` (compose: `http://objectstore:8333`) | S3 endpoint the backend uses. Point at AWS S3 or R2 in production |
| `RESUME_S3_PUBLIC_URL` | no | unset | Endpoint the **browser** can reach, used to sign view links (compose: `http://localhost:8333`). Unset means the internal endpoint |
| `RESUME_S3_REGION` | no | `us-east-1` | Signing region |
| `RESUME_MAX_BYTES` | no | `5242880` | Resume size cap (PDF only, magic bytes checked) |
| `RESUME_URL_EXPIRY_SECONDS` | no | `300` | Lifetime of signed resume view links |
| `GITHUB_TOKEN` | no | unset | Optional token for the coding-activity sync (raises GitHub's limit from 60 requests/hour) |

## Frontend and test tooling

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `BACKEND_URL` | Next.js | `http://localhost:8000` (compose: `http://backend:8000`) | Target of the `/api/v1/*` rewrite |
| `API_SCHEMA_URL` | `npm run gen:api` | `http://localhost:8000/api/v1/schema/` | Schema source for generated types |
| `E2E_BASE_URL` | Playwright | `http://localhost:3000` | App under test |
| `E2E_PASSWORD` | Playwright | `Demo-Pass-2026` | Password given to `seed_demo` |
