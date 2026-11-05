import { ApiError } from "./client";
import { apiFetch } from "./http";

/**
 * JSON request helper for endpoints whose payloads are typed by hand in `types.ts` (reports and
 * dashboards return computed objects). Everything else uses the generated `api` client.
 */
export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const base = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const response = await apiFetch(
    new Request(new URL(path, base), {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
  const text = await response.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

export const get = <T>(path: string) => request<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});
export const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
export const del = <T>(path: string) => request<T>("DELETE", path);

/** Multipart upload (resume PDFs). The browser sets the multipart boundary itself. */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const response = await apiFetch(new Request(new URL(path, window.location.origin), { method: "POST", body: form }));
  const text = await response.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

/** Fetch a file (Excel exports) and hand it to the browser as a download. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const response = await apiFetch(new Request(new URL(path, window.location.origin), { method: "GET" }));
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text ? JSON.parse(text) : undefined);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Build a query string from filters, dropping empty values. */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
  const s = search.toString();
  return s ? `?${s}` : "";
}
