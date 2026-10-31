# ADR 0008: TOTP MFA implemented with the standard library

- Status: accepted (2026-10-21)

## Context
CES requires TOTP MFA for admin roles. The plan mentioned django-otp, which brings session-based plumbing this cookie-JWT API doesn't use.

## Decision
- Implement RFC 6238 (`apps/accounts/totp.py`, about 50 lines, `hmac`/`hashlib`), verified against the RFC's published test vectors, with ±1-step drift tolerance and anti-replay via the last accepted counter.
- Login becomes two-step: after the password, a signed 5-minute challenge cookie must be followed by a valid code.
- Roles in `MFA_REQUIRED_ROLES` get a restricted session (`/auth/*` only) until they enrol.

## Consequences
- No new dependency.
- The secret is stored in plain form in the database: field-level encryption remains open technical debt.
- Recovery codes are not implemented. A superuser resets a lost device in Django admin.
