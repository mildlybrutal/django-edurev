# ADR 0002: SimpleJWT in httpOnly cookies, with portal-bound tokens

- Status: accepted (2026-10-20)

## Context
CES requires SimpleJWT on Paths P2/P3. P06 §16 requires that the recruiter portal does not share the session cookie domain or throttle scope with the rest of the app. Tokens in localStorage are exposed to XSS.

## Decision
- Access and refresh tokens are stored only in httpOnly cookies (`pa_access` on `/`, `pa_refresh` on `/api/v1/auth/`). `Authorization: Bearer` is not accepted.
- Cookie auth requires CSRF protection on unsafe methods (Django's double-submit `csrftoken`).
- Refresh tokens rotate on every use and the old one is blacklisted.
- Every token carries a `portal` claim (`internal` | `recruiter`). Each portal has its own authentication class, cookie names and paths, and its own throttle scopes. Recruiters cannot obtain internal tokens. In production the recruiter portal is served from its own host, so its cookies never share a domain with the internal portal.

## Consequences
- JavaScript never sees tokens. A stolen internal token is useless on recruiter endpoints and vice versa.
- Clients must fetch `/auth/csrf/` before the first unsafe request (the frontend wrapper does this).
- Logout is effective for the refresh token immediately. An access token stays valid until it expires (10 minutes by default).
