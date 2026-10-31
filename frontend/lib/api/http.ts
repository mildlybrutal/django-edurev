/**
 * Browser fetch for the Django API. All calls are same-origin (`/api/v1/...` is proxied to
 * Django), so httpOnly auth cookies travel automatically. This wrapper only:
 *  - adds Django's CSRF header to unsafe requests, and
 *  - on a 401, refreshes the session once and retries.
 * It never sees or stores tokens. Authorization is decided by the server.
 */

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const AUTH_PREFIX = "/api/v1/auth/";
const RECRUITER_PREFIX = "/api/v1/recruiter/";
const RECRUITER_AUTH_PREFIX = "/api/v1/recruiter/auth/";

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

async function ensureCsrfCookie(): Promise<string> {
  let token = readCookie("csrftoken");
  if (!token) {
    await fetch(`${AUTH_PREFIX}csrf/`, { credentials: "same-origin" });
    token = readCookie("csrftoken");
  }
  return token ?? "";
}

const refreshInFlight: Record<string, Promise<boolean> | null> = {};

/**
 * Rotate the session using the refresh cookie of the given portal (internal and recruiter
 * sessions are separate). Concurrent callers share one request.
 */
export function refreshSession(prefix: string = AUTH_PREFIX): Promise<boolean> {
  refreshInFlight[prefix] ??= ensureCsrfCookie()
    .then((csrf) =>
      fetch(`${prefix}refresh/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf },
      }),
    )
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight[prefix] = null;
    });
  return refreshInFlight[prefix];
}

function pathOf(url: string): string {
  return new URL(url, "http://localhost").pathname;
}

function isAuthEndpoint(url: string): boolean {
  const path = pathOf(url);
  return path.startsWith(AUTH_PREFIX) || path.startsWith(RECRUITER_AUTH_PREFIX);
}

export async function apiFetch(request: Request): Promise<Response> {
  const unsafe = !SAFE_METHODS.has(request.method.toUpperCase());
  const retryCopy = request.clone();

  const send = async (req: Request) => {
    const headers = new Headers(req.headers);
    if (unsafe) headers.set("X-CSRFToken", await ensureCsrfCookie());
    return fetch(new Request(req, { headers, credentials: "same-origin" }));
  };

  const response = await send(request);
  if (response.status !== 401 || isAuthEndpoint(request.url)) return response;
  const prefix = pathOf(request.url).startsWith(RECRUITER_PREFIX) ? RECRUITER_AUTH_PREFIX : AUTH_PREFIX;
  return (await refreshSession(prefix)) ? send(retryCopy) : response;
}
