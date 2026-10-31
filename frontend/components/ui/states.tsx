import type { ReactNode } from "react";
import { ApiError } from "@/lib/api/client";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p role="status" className="py-6 text-sm text-muted">
      {label}
    </p>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body as Record<string, unknown> | undefined;
    if (body && typeof body === "object") {
      if (typeof body.detail === "string") return body.detail;
      const first = Object.entries(body)[0];
      if (first) {
        const [field, value] = first;
        const text = Array.isArray(value) ? String(value[0]) : typeof value === "string" ? value : "";
        if (text) return field === "non_field_errors" || field === "detail" ? text : `${field}: ${text}`;
      }
    }
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
      {errorMessage(error)}
    </p>
  );
}

/** Render loading / error / content for a query without repeating the boilerplate. */
export function QueryState<T>({
  query,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined };
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorNote error={query.error} />;
  return <>{children(query.data as T)}</>;
}
