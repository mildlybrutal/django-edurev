# ADR 0003: Same-origin API proxy; authenticated data fetched client-side

- Status: accepted (2026-10-20)

## Context
The Next.js 16 scaffold enables `cacheComponents`. Server-rendering authenticated data under this model requires careful `use cache: private` / Suspense handling, and a mistake can cache one user's data for another. Recruiter data is the highest-risk surface (P06 §8).

## Decision
- The browser only talks to the Next origin. `/api/v1/*` is rewritten to Django, so cookies are first-party and no CORS configuration exists.
- Pages are static shells. Authenticated data is fetched in client components with TanStack Query through a typed `openapi-fetch` client.
- Django adds its own `Cache-Control` where needed (recruiter responses: `no-store`, Phase 11).

## Consequences
- No user data passes through Next's server-side caches.
- There is no SSR/SEO for authenticated pages. That's acceptable because none of them are public.
- The rewrite adds a trailing slash because Next strips it and Django routes require it.
