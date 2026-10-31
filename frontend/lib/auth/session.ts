"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { get, post } from "@/lib/api/request";

export type Me = Schemas["Me"];
export type AuthPortal = "internal" | "recruiter";

export const meQueryKey = ["auth", "me"] as const;
export const recruiterMeQueryKey = ["auth", "recruiter-me"] as const;

const AUTH_BASE: Record<AuthPortal, string> = {
  internal: "/api/v1/auth/",
  recruiter: "/api/v1/recruiter/auth/",
};

/** Current internal-portal user, or null when not signed in. */
export function useMe() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return unwrap(await api.GET("/api/v1/auth/me/"));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

/** Current recruiter-portal user (separate session and cookies), or null. */
export function useRecruiterMe() {
  return useQuery({
    queryKey: recruiterMeQueryKey,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await get<Me>("/api/v1/recruiter/me/");
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
        throw error;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export type LoginOutcome = { kind: "signed_in"; me: Me } | { kind: "mfa_required" };

export function useLogin(portal: AuthPortal = "internal") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }): Promise<LoginOutcome> => {
      const result = await post<Me & { mfa_required?: boolean }>(`${AUTH_BASE[portal]}login/`, credentials);
      return result.mfa_required ? { kind: "mfa_required" } : { kind: "signed_in", me: result };
    },
    onSuccess: (outcome) => {
      if (outcome.kind === "signed_in") {
        queryClient.clear();
        queryClient.setQueryData(portal === "internal" ? meQueryKey : recruiterMeQueryKey, outcome.me);
      }
    },
  });
}

export function useVerifyMfa(portal: AuthPortal = "internal") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => post<Me>(`${AUTH_BASE[portal]}mfa/verify/`, { code }),
    onSuccess: (me) => {
      queryClient.clear();
      queryClient.setQueryData(portal === "internal" ? meQueryKey : recruiterMeQueryKey, me);
    },
  });
}

export function useLogout(portal: AuthPortal = "internal") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await post(`${AUTH_BASE[portal]}logout/`);
    },
    onSettled: () => {
      // Drop every cached response so nothing from this session survives sign-out.
      queryClient.clear();
      queryClient.setQueryData(portal === "internal" ? meQueryKey : recruiterMeQueryKey, null);
    },
  });
}
