import createClient from "openapi-fetch";
import { apiFetch } from "./http";
import type { components, paths } from "./schema";

/** Typed client for the Django API. Types are generated from the DRF OpenAPI schema (`npm run gen:api`). */
export const api = createClient<paths>({
  // Same-origin in the browser; an absolute base keeps non-browser runtimes (tests) happy too.
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  fetch: apiFetch,
});

export type Schemas = components["schemas"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(typeof body === "object" && body && "detail" in body ? String(body.detail) : `Request failed (${status})`);
  }
}

/** Unwrap an openapi-fetch result, throwing ApiError on failure. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiError(result.response.status, result.error);
  }
  return result.data as T;
}
