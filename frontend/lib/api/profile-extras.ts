"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, get, patch, post, upload } from "./request";

/* Coding activity (GitHub / LeetCode ratings) and resumes. Payloads are computed objects, so
 * they are typed here rather than generated. */

export type RatingComponent = {
  key: string;
  label: string;
  value: number;
  cap: number;
  weight: number;
  points: number;
};

export type CodingProfile = {
  id: number;
  platform: "github" | "leetcode";
  platform_label: string;
  username: string;
  status: "pending" | "ok" | "not_found" | "error";
  status_label: string;
  score: number | null;
  stats: Record<string, unknown>;
  explanation: { summary?: string; components?: RatingComponent[] };
  error: string;
  last_synced_at: string | null;
  verification_status: string | null;
};

export type CodingPayload = {
  coding_activity: number | null;
  profiles: CodingProfile[];
  note: string;
  queued?: number;
};

export type Resume = { id: number; name: string; size: number; uploaded_at: string; url: string; expires_in: number };

export type Onboarding = {
  required: boolean;
  github?: boolean;
  leetcode?: boolean;
  linkedin?: boolean;
  resume?: boolean;
};

export const GITHUB_USERNAME = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/;
export const LEETCODE_USERNAME = /^[A-Za-z0-9_-]{1,30}$/;

/** Accept a pasted profile URL or @handle and reduce it to the username. */
export function handleFrom(value: string, host: "github.com" | "leetcode.com"): string {
  const v = value.trim().replace(/^@/, "");
  try {
    const url = new URL(v.includes("://") ? v : `https://${v}`);
    if (url.hostname.replace(/^www\./, "") === host) {
      const parts = url.pathname.split("/").filter(Boolean);
      return (host === "leetcode.com" && (parts[0] === "u" || parts[0] === "profile") ? parts[1] : parts[0]) ?? "";
    }
  } catch {
    // Not a URL: treat as a bare username.
  }
  return v;
}

export const codingKey = (student: string | number) => ["coding", String(student)];
export const resumeKey = (student: string | number) => ["resume", String(student)];

export function useCoding(student: string | number = "me") {
  return useQuery({
    queryKey: codingKey(student),
    queryFn: () => get<CodingPayload>(`/api/v1/students/${student}/coding/`),
    // Poll while a sync is in flight so the rating appears without a reload.
    refetchInterval: (q) => (q.state.data?.profiles.some((p) => p.status === "pending") ? 3000 : false),
  });
}

export function useResume(student: string | number = "me", enabled = true) {
  return useQuery({
    queryKey: resumeKey(student),
    enabled,
    retry: false,
    queryFn: async () => {
      try {
        return await get<Resume>(`/api/v1/students/${student}/resume/`);
      } catch (e) {
        if ((e as { status?: number }).status === 404) return null;
        throw e;
      }
    },
  });
}

function useInvalidateProfile() {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["coding"] }),
      qc.invalidateQueries({ queryKey: ["resume"] }),
      qc.invalidateQueries({ queryKey: ["onboarding"] }),
      qc.invalidateQueries({ queryKey: ["student"] }),
      qc.invalidateQueries({ queryKey: ["profile"] }),
      qc.invalidateQueries({ queryKey: ["dashboard"] }),
      qc.invalidateQueries({ queryKey: ["evidence"] }),
    ]);
}

export function useSaveCoding() {
  const refresh = useInvalidateProfile();
  return useMutation({
    meta: { toast: "Coding profiles saved", toastBody: "Ratings appear once each platform has synced." },
    mutationFn: async ({ github, leetcode }: { github?: string; leetcode?: string }) => {
      const result = await post<CodingPayload>("/api/v1/students/me/coding/", {
        ...(github !== undefined && { github_username: github }),
        ...(leetcode !== undefined && { leetcode_username: leetcode }),
      });
      if (github !== undefined)
        await patch("/api/v1/students/me/", { github_url: github ? `https://github.com/${github}` : "" });
      return result;
    },
    onSuccess: refresh,
  });
}

export function useRefreshCoding() {
  const refresh = useInvalidateProfile();
  return useMutation({
    meta: {
      toast: (_: never, data: never) =>
        (data as CodingPayload).queued ? "Sync started" : "Already up to date (synced in the last 30 minutes)",
    },
    mutationFn: () => post<CodingPayload>("/api/v1/students/me/coding/refresh/"),
    onSuccess: refresh,
  });
}

export function useUploadResume() {
  const refresh = useInvalidateProfile();
  return useMutation({
    meta: { toast: "Resume uploaded" },
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return upload<Resume>("/api/v1/students/me/resume/", form);
    },
    onSuccess: refresh,
  });
}

export function useDeleteResume() {
  const refresh = useInvalidateProfile();
  return useMutation({
    meta: { toast: "Resume removed" },
    mutationFn: () => del("/api/v1/students/me/resume/"),
    onSuccess: refresh,
  });
}

export const RESUME_MAX_BYTES = 5 * 1024 * 1024;

/** Client-side pre-check; the server re-validates (size, extension, PDF magic bytes). */
export function resumeProblem(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) return "Upload your resume as a PDF file.";
  if (file.size > RESUME_MAX_BYTES) return "Resume must be 5 MB or smaller.";
  return null;
}
