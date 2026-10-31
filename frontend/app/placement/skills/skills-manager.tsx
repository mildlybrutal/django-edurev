"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { SkillPicker } from "@/components/domain/skill-picker";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { Tabs } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/client";
import {
  useAddParent,
  useAddSynonym,
  useClusters,
  useCreateSkill,
  useMergeSkill,
  useRemoveParent,
  useRemoveSynonym,
  useSkill,
  useSkills,
  useTargetRoles,
  type TargetRole,
} from "@/lib/api/taxonomy";
import { del, post } from "@/lib/api/request";
import { useMe } from "@/lib/auth/session";
import { cn } from "@/lib/cn";

type Tab = "skills" | "roles";

export function SkillsManager() {
  const { data: me } = useMe();
  const isAdmin = !!me?.roles.includes("admin");
  const [tab, setTab] = useState<Tab>("skills");

  return (
    <>
      <PageHeader
        title="Manage Skills"
        description={
          isAdmin
            ? "The institutional skill taxonomy used for matching. Changes are audited."
            : "The institutional skill taxonomy used for matching. Only administrators can edit it."
        }
      />
      <Tabs
        label="Taxonomy sections"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "skills", label: "Skills" },
          { value: "roles", label: "Target roles" },
        ]}
      />
      {tab === "skills" ? <SkillsTab isAdmin={isAdmin} /> : <RolesTab isAdmin={isAdmin} />}
    </>
  );
}

function SkillsTab({ isAdmin }: { isAdmin: boolean }) {
  const [query, setQuery] = useState("");
  const [cluster, setCluster] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: clusters } = useClusters();
  const { data, isPending, isError } = useSkills(query.trim(), cluster, page);

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card>
        <CardHeader title="Skills" description={data ? `${data.count} skills` : undefined} />
        <div className="flex flex-wrap gap-2 border-b border-border px-5 py-3">
          <label className="sr-only" htmlFor="skill-search">
            Search skills
          </label>
          <input
            id="skill-search"
            type="search"
            placeholder="Search names and synonyms…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            className="h-8 min-w-48 flex-1 rounded-md border border-border bg-surface px-2.5 text-sm placeholder:text-muted"
          />
          <label className="sr-only" htmlFor="cluster-filter">
            Cluster
          </label>
          <select
            id="cluster-filter"
            value={cluster}
            onChange={(e) => {
              setCluster(e.target.value);
              setPage(1);
            }}
            className="h-8 rounded-md border border-border bg-surface px-2 text-sm"
          >
            <option value="">All clusters</option>
            {clusters?.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        {isError ? (
          <CardBody className="text-sm text-danger">Could not load skills.</CardBody>
        ) : isPending ? (
          <CardBody className="text-sm text-muted">Loading…</CardBody>
        ) : data.results.length === 0 ? (
          <CardBody>
            <EmptyState title="No skills match">Try another search or cluster.</EmptyState>
          </CardBody>
        ) : (
          <ul className="max-h-[32rem] divide-y divide-border overflow-y-auto">
            {data.results.map((skill) => (
              <li key={skill.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(skill.id)}
                  aria-pressed={skill.id === selectedId}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-5 py-2.5 text-left text-sm hover:bg-surface-muted",
                    skill.id === selectedId && "bg-primary-soft",
                  )}
                >
                  <span className="min-w-0">
                    <span className="font-medium">{skill.name}</span>
                    {skill.synonyms.length > 0 && (
                      <span className="ml-2 truncate text-xs text-muted">
                        {skill.synonyms.map((s) => s.name).join(", ")}
                      </span>
                    )}
                  </span>
                  <span className="flex shrink-0 gap-1.5">
                    {skill.is_abstract && <Badge tone="info">Category</Badge>}
                    {skill.cluster && <Badge>{skill.cluster.name}</Badge>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {data && !query && (data.next || data.previous) && (
          <div className="flex items-center justify-between border-t border-border px-5 py-2.5 text-sm">
            <Button variant="ghost" disabled={!data.previous} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-muted">Page {page}</span>
            <Button variant="ghost" disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        )}
      </Card>

      <div className="flex flex-col gap-5">
        {selectedId !== null ? (
          <SkillDetailCard id={selectedId} isAdmin={isAdmin} onMerged={setSelectedId} />
        ) : (
          <EmptyState title="Select a skill">See its synonyms and how it relates to other skills.</EmptyState>
        )}
        {isAdmin && <NewSkillCard onCreated={setSelectedId} />}
      </div>
    </div>
  );
}

function errorText(error: unknown): string | undefined {
  if (!error) return undefined;
  if (error instanceof ApiError) {
    const body = error.body as Record<string, unknown> | undefined;
    const first = body && Object.values(body)[0];
    return Array.isArray(first) ? String(first[0]) : error.message;
  }
  return "Something went wrong.";
}

function SkillDetailCard({
  id,
  isAdmin,
  onMerged,
}: {
  id: number;
  isAdmin: boolean;
  onMerged: (targetId: number) => void;
}) {
  const { data: skill, isPending } = useSkill(id);
  const addSynonym = useAddSynonym(id);
  const removeSynonym = useRemoveSynonym(id);
  const addParent = useAddParent(id);
  const removeParent = useRemoveParent(id);
  const merge = useMergeSkill(id);
  const [synonym, setSynonym] = useState("");

  if (isPending || !skill) {
    return <Card className="px-5 py-4 text-sm text-muted">Loading…</Card>;
  }

  const error = errorText(addSynonym.error ?? addParent.error ?? merge.error ?? removeParent.error);

  return (
    <Card>
      <CardHeader
        title={skill.name}
        description={skill.cluster?.name ?? "No cluster"}
        action={skill.is_abstract ? <Badge tone="info">Category</Badge> : undefined}
      />
      <CardBody className="flex flex-col gap-5 text-sm">
        {skill.description && <p className="text-muted">{skill.description}</p>}

        <section aria-labelledby="synonyms-heading">
          <h3 id="synonyms-heading" className="mb-2 text-sm font-semibold">
            Synonyms
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {skill.synonyms.length === 0 && <span className="text-muted">None</span>}
            {skill.synonyms.map((s) => (
              <span key={s.id} className="inline-flex items-center gap-1 rounded-full bg-surface-muted px-2.5 py-0.5">
                {s.name}
                {isAdmin && (
                  <button
                    type="button"
                    aria-label={`Remove synonym ${s.name}`}
                    className="text-muted hover:text-danger"
                    onClick={() => removeSynonym.mutate(s.id)}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
          </div>
          {isAdmin && (
            <form
              className="mt-2 flex gap-2"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                addSynonym.mutate(synonym.trim(), { onSuccess: () => setSynonym("") });
              }}
            >
              <label htmlFor="new-synonym" className="sr-only">
                New synonym
              </label>
              <input
                id="new-synonym"
                value={synonym}
                onChange={(e) => setSynonym(e.target.value)}
                placeholder="Add a synonym"
                className="h-8 flex-1 rounded-md border border-border bg-surface px-2.5 text-sm placeholder:text-muted"
              />
              <Button type="submit" variant="secondary" disabled={!synonym.trim() || addSynonym.isPending}>
                Add
              </Button>
            </form>
          )}
        </section>

        <section aria-labelledby="satisfies-heading">
          <h3 id="satisfies-heading" className="mb-1 text-sm font-semibold">
            Satisfies requirements for
          </h3>
          <p className="mb-2 text-xs text-muted">A student with {skill.name} matches a requirement for any of these.</p>
          <RelationList
            items={skill.parents}
            onRemove={isAdmin ? (parentId) => removeParent.mutate(parentId) : undefined}
          />
          {isAdmin && (
            <div className="mt-2">
              <SkillPicker
                label="Link to a broader skill…"
                exclude={[skill.id, ...skill.parents.map((p) => p.id)]}
                onPick={(parent) => addParent.mutate(parent.id)}
              />
            </div>
          )}
        </section>

        <section aria-labelledby="satisfied-heading">
          <h3 id="satisfied-heading" className="mb-2 text-sm font-semibold">
            Satisfied by
          </h3>
          <RelationList items={skill.children} />
        </section>

        {isAdmin && (
          <section aria-labelledby="merge-heading" className="border-t border-border pt-4">
            <h3 id="merge-heading" className="mb-1 text-sm font-semibold">
              Merge into another skill
            </h3>
            <p className="mb-2 text-xs text-muted">
              {skill.name} becomes a synonym of the chosen skill and is retired. Its links and role mappings move
              across.
            </p>
            <SkillPicker
              label="Merge into…"
              exclude={[skill.id]}
              onPick={(target) => merge.mutate(target.id, { onSuccess: () => onMerged(target.id) })}
            />
          </section>
        )}

        {error && (
          <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-danger">
            {error}
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function RelationList({ items, onRemove }: { items: { id: number; name: string }[]; onRemove?: (id: number) => void }) {
  if (items.length === 0) return <p className="text-muted">None</p>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li
          key={item.id}
          className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2.5 py-0.5 text-primary"
        >
          {item.name}
          {onRemove && (
            <button
              type="button"
              aria-label={`Remove link to ${item.name}`}
              className="hover:text-danger"
              onClick={() => onRemove(item.id)}
            >
              ×
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function NewSkillCard({ onCreated }: { onCreated: (id: number) => void }) {
  const { data: clusters } = useClusters();
  const create = useCreateSkill();
  const [name, setName] = useState("");
  const [clusterId, setClusterId] = useState("");
  const [isAbstract, setIsAbstract] = useState(false);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        name: name.trim(),
        description: "",
        is_abstract: isAbstract,
        cluster_id: clusterId ? Number(clusterId) : null,
        parent_ids: [],
      },
      {
        onSuccess: (skill) => {
          setName("");
          setIsAbstract(false);
          onCreated(skill.id);
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader title="Add a skill" />
      <CardBody>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="new-skill-cluster" className="text-sm font-medium">
              Cluster
            </label>
            <select
              id="new-skill-cluster"
              value={clusterId}
              onChange={(e) => setClusterId(e.target.value)}
              className="h-9 rounded-md border border-border bg-surface px-2 text-sm"
            >
              <option value="">None</option>
              {clusters?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isAbstract} onChange={(e) => setIsAbstract(e.target.checked)} />
            Category (e.g. “Frontend Framework”) that other skills satisfy
          </label>
          {create.error && (
            <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
              {errorText(create.error)}
            </p>
          )}
          <Button type="submit" disabled={!name.trim() || create.isPending}>
            Add skill
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function RolesTab({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const { data: roles, isPending, isError } = useTargetRoles();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cluster, setCluster] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
  const createRole = useMutation({
    meta: { toast: "Role created" },
    mutationFn: () => post("/api/v1/skills/roles/", { name, description }),
    onSuccess: () => {
      setName("");
      setDescription("");
      refresh();
    },
  });
  const createCluster = useMutation({
    meta: { toast: "Cluster created" },
    mutationFn: () => post("/api/v1/skills/clusters/", { name: cluster, description: "" }),
    onSuccess: () => {
      setCluster("");
      refresh();
    },
  });
  if (isError) return <p className="text-sm text-danger">Could not load target roles.</p>;
  if (isPending) return <p className="text-sm text-muted">Loading…</p>;

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <p className="text-sm text-muted xl:col-span-2">
        Role templates the placement cell can start a drive&apos;s requirements from. Levels and weights are institution
        configuration{isAdmin ? "" : ", editable by administrators"}.
      </p>
      {roles.length === 0 && <EmptyState title="No target roles yet" />}
      {roles.map((role) => (
        <RoleCard key={role.id} role={role} isAdmin={isAdmin} onChange={refresh} />
      ))}
      {isAdmin && (
        <Card>
          <CardHeader title="Add a target role" />
          <CardBody className="flex flex-col gap-3">
            <TextField label="Role name" value={name} onChange={(e) => setName(e.target.value)} />
            <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
            {createRole.error ? (
              <p role="alert" className="text-sm text-danger">
                {errorText(createRole.error)}
              </p>
            ) : null}
            <Button
              className="self-start"
              disabled={!name.trim() || createRole.isPending}
              onClick={() => createRole.mutate()}
            >
              Add role
            </Button>
            <hr className="border-border" />
            <TextField label="New skill cluster" value={cluster} onChange={(e) => setCluster(e.target.value)} />
            {createCluster.error ? (
              <p role="alert" className="text-sm text-danger">
                {errorText(createCluster.error)}
              </p>
            ) : null}
            <Button
              variant="secondary"
              className="self-start"
              disabled={!cluster.trim() || createCluster.isPending}
              onClick={() => createCluster.mutate()}
            >
              Add cluster
            </Button>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

const LEVEL_NAMES = ["None", "Beginner", "Intermediate", "Advanced", "Expert"];

function RoleCard({ role, isAdmin, onChange }: { role: TargetRole; isAdmin: boolean; onChange: () => void }) {
  const [pending, setPending] = useState<{ id: number; name: string } | null>(null);
  const [level, setLevel] = useState(2);
  const [weight, setWeight] = useState(2);
  const [core, setCore] = useState(false);
  const add = useMutation({
    meta: { toast: "Skill added to role" },
    mutationFn: () =>
      post(`/api/v1/skills/roles/${role.id}/skills/`, {
        skill_id: pending!.id,
        required_level: level,
        weight,
        is_core: core,
      }),
    onSuccess: () => {
      setPending(null);
      onChange();
    },
  });
  const remove = useMutation({
    meta: { toast: "Skill removed from role" },
    mutationFn: (skillId: number) => del(`/api/v1/skills/roles/${role.id}/skills/${skillId}/`),
    onSuccess: onChange,
  });
  return (
    <Card>
      <CardHeader title={role.name} description={role.description} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th scope="col" className="px-5 py-2 font-medium">
                Skill
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Required level
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Weight
              </th>
              {isAdmin && (
                <th scope="col" className="px-3 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {role.role_skills.map((rs) => (
              <tr key={rs.id}>
                <td className="px-5 py-2">
                  {rs.skill.name} {rs.is_core && <Badge tone="primary">Core</Badge>}
                </td>
                <td className="px-3 py-2">{rs.required_level_label}</td>
                <td className="px-3 py-2 text-right tabular-nums">{rs.weight}</td>
                {isAdmin && (
                  <td className="px-3 py-2 text-right">
                    <Button
                      variant="ghost"
                      onClick={() => remove.mutate(rs.skill.id)}
                      aria-label={`Remove ${rs.skill.name}`}
                    >
                      Remove
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isAdmin && (
        <CardBody className="border-t border-border">
          {pending ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{pending.name}</span>
              <select
                aria-label="Required level"
                value={level}
                onChange={(e) => setLevel(Number(e.target.value))}
                className="h-8 rounded-md border border-border bg-surface px-2"
              >
                {[1, 2, 3, 4].map((l) => (
                  <option key={l} value={l}>
                    {LEVEL_NAMES[l]}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1">
                Weight
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={weight}
                  onChange={(e) => setWeight(Number(e.target.value))}
                  className="h-8 w-16 rounded-md border border-border bg-surface px-2"
                />
              </label>
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={core} onChange={(e) => setCore(e.target.checked)} />
                Core
              </label>
              <Button onClick={() => add.mutate()} disabled={add.isPending}>
                Add
              </Button>
              <Button variant="ghost" onClick={() => setPending(null)}>
                Cancel
              </Button>
            </div>
          ) : (
            <SkillPicker
              label="Add a skill to this role…"
              exclude={role.role_skills.map((rs) => rs.skill.id)}
              onPick={(s) => setPending({ id: s.id, name: s.name })}
            />
          )}
          {add.error ? (
            <p role="alert" className="mt-2 text-sm text-danger">
              {errorText(add.error)}
            </p>
          ) : null}
        </CardBody>
      )}
    </Card>
  );
}
