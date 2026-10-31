"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "./client";

export type Skill = Schemas["Skill"];
export type SkillDetail = Schemas["SkillDetail"];
export type SkillCluster = Schemas["SkillCluster"];
export type TargetRole = Schemas["TargetRole"];

const keys = {
  all: ["taxonomy"] as const,
  skills: (q: string, cluster: string, page: number) => ["taxonomy", "skills", q, cluster, page] as const,
  skill: (id: number) => ["taxonomy", "skill", id] as const,
  clusters: ["taxonomy", "clusters"] as const,
  roles: ["taxonomy", "roles"] as const,
};

export function useSkills(q: string, cluster: string, page: number) {
  return useQuery({
    queryKey: keys.skills(q, cluster, page),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/skills/", {
          params: { query: { q: q || undefined, cluster: cluster || undefined, page: q ? undefined : page } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function useSkill(id: number | null) {
  return useQuery({
    queryKey: keys.skill(id ?? 0),
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/{id}/", { params: { path: { id: id! } } })),
    enabled: id !== null,
  });
}

export function useClusters() {
  return useQuery({
    queryKey: keys.clusters,
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/clusters/")).results,
    staleTime: 5 * 60_000,
  });
}

export function useTargetRoles() {
  return useQuery({
    queryKey: keys.roles,
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/roles/")).results,
  });
}

/** Wraps a taxonomy write so every cached taxonomy query refreshes afterwards. */
function useTaxonomyMutation<TVars, TResult>(toast: string, fn: (vars: TVars) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { toast },
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useCreateSkill() {
  return useTaxonomyMutation("Skill created", async (body: Schemas["SkillWrite"]) =>
    unwrap(await api.POST("/api/v1/skills/", { body })),
  );
}

export function useAddSynonym(skillId: number) {
  return useTaxonomyMutation("Synonym added", async (name: string) =>
    unwrap(await api.POST("/api/v1/skills/{id}/synonyms/", { params: { path: { id: skillId } }, body: { name } })),
  );
}

export function useRemoveSynonym(skillId: number) {
  return useTaxonomyMutation("Synonym removed", async (synonymId: number) => {
    const result = await api.DELETE("/api/v1/skills/{id}/synonyms/{synonym_id}/", {
      params: { path: { id: skillId, synonym_id: String(synonymId) } },
    });
    if (!result.response.ok) unwrap(result);
  });
}

export function useAddParent(skillId: number) {
  return useTaxonomyMutation("Parent skill linked", async (parentId: number) =>
    unwrap(
      await api.POST("/api/v1/skills/{id}/parents/", {
        params: { path: { id: skillId } },
        body: { skill_id: parentId },
      }),
    ),
  );
}

export function useRemoveParent(skillId: number) {
  return useTaxonomyMutation("Parent skill unlinked", async (parentId: number) => {
    const result = await api.DELETE("/api/v1/skills/{id}/parents/{parent_id}/", {
      params: { path: { id: skillId, parent_id: String(parentId) } },
    });
    if (!result.response.ok) unwrap(result);
  });
}

export function useMergeSkill(skillId: number) {
  return useTaxonomyMutation("Skills merged", async (targetId: number) =>
    unwrap(
      await api.POST("/api/v1/skills/{id}/merge/", {
        params: { path: { id: skillId } },
        body: { skill_id: targetId },
      }),
    ),
  );
}
