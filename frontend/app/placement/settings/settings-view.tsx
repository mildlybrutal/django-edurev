"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { patch, post } from "@/lib/api/request";
import { useMe } from "@/lib/auth/session";

const LEVELS = ["None", "Beginner", "Intermediate", "Advanced", "Expert"];

export function SettingsView() {
  const { data: me } = useMe();
  const isAdmin = !!me?.roles.includes("admin");
  return (
    <>
      <PageHeader
        title="Scoring & Rubrics"
        description="How evidence turns into skill levels and readiness. These are implementation choices of this platform, configurable per institution — not values from the P06 specification."
      />
      <div className="flex flex-col gap-5">
        <ScoringConfig isAdmin={isAdmin} />
        <EvidenceRules isAdmin={isAdmin} />
        <Rubrics />
      </div>
    </>
  );
}

function ScoringConfig({ isAdmin }: { isAdmin: boolean }) {
  const config = useQuery({
    queryKey: ["readiness", "config"],
    queryFn: async () => unwrap(await api.GET("/api/v1/readiness/config/")),
  });
  return (
    <Card>
      <CardHeader
        title="Readiness model"
        description={
          config.data
            ? `Active version v${config.data.version}. Publishing creates a new version; existing snapshots keep the version that produced them.`
            : undefined
        }
      />
      <CardBody>
        <QueryState query={config}>{(c) => <ScoringForm key={c.version} config={c} isAdmin={isAdmin} />}</QueryState>
      </CardBody>
    </Card>
  );
}

function ScoringForm({ config, isAdmin }: { config: Schemas["ScoringConfig"]; isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(config).map(([k, v]) => [k, String(v)])),
  );
  const publish = useMutation({
    meta: { toast: "New scoring version published", toastBody: "Run batch readiness to apply it to everyone." },
    mutationFn: () =>
      post("/api/v1/readiness/config/", {
        weight_technical: Number(form.weight_technical),
        weight_aptitude: Number(form.weight_aptitude),
        weight_communication: Number(form.weight_communication),
        weight_project_depth: Number(form.weight_project_depth),
        weight_coding: Number(form.weight_coding),
        unverified_multiplier: form.unverified_multiplier,
        technical_top_n: Number(form.technical_top_n),
        recent_window: Number(form.recent_window),
        project_target: Number(form.project_target),
        ready_threshold: Number(form.ready_threshold),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["readiness"] }),
  });
  const field = (key: string, label: string, props: Record<string, unknown> = {}) => (
    <TextField
      label={label}
      type="number"
      value={form[key] ?? ""}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      disabled={!isAdmin}
      {...props}
    />
  );
  return (
    <form
      className="grid gap-3 md:grid-cols-4"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        publish.mutate();
      }}
    >
      {field("weight_technical", "Weight: technical mastery", { min: 0 })}
      {field("weight_aptitude", "Weight: aptitude", { min: 0 })}
      {field("weight_communication", "Weight: communication", { min: 0 })}
      {field("weight_project_depth", "Weight: project depth", { min: 0 })}
      {field("weight_coding", "Weight: coding activity", { min: 0 })}
      {field("unverified_multiplier", "Unverified evidence credit (0–1)", { min: 0, max: 1, step: "0.05" })}
      {field("technical_top_n", "Skills counted (general technical)", { min: 1 })}
      {field("recent_window", "Latest assessments averaged", { min: 1 })}
      {field("project_target", "Projects for full project depth", { min: 1 })}
      {field("ready_threshold", "Ready at (%)", { min: 0, max: 100 })}
      {isAdmin ? (
        <div className="flex flex-col gap-2 md:col-span-4">
          {publish.error ? <FormError message={errorMessage(publish.error)} /> : null}
          <Button type="submit" className="self-start" disabled={publish.isPending}>
            Publish new version
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted md:col-span-4">Only administrators can change the readiness model.</p>
      )}
    </form>
  );
}

function EvidenceRules({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const rules = useQuery({
    queryKey: ["readiness", "rules"],
    queryFn: async () => unwrap(await api.GET("/api/v1/readiness/evidence-rules/")),
  });
  const update = useMutation({
    meta: { toast: "Evidence rule updated" },
    mutationFn: ({ id, key, value }: { id: number; key: string; value: number }) =>
      patch(`/api/v1/readiness/evidence-rules/${id}/`, { [key]: value }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["readiness", "rules"] }),
  });
  const select = (rule: Schemas["EvidenceRule"], key: "max_level_unverified" | "max_level_verified") => (
    <select
      aria-label={`${rule.source_label} ${key.replace(/_/g, " ")}`}
      value={rule[key]}
      disabled={!isAdmin || update.isPending}
      onChange={(e) => update.mutate({ id: rule.id, key, value: Number(e.target.value) })}
      className="h-8 rounded-md border border-border bg-surface px-2 text-sm"
    >
      {LEVELS.map(
        (l, i) =>
          i > 0 && (
            <option key={l} value={i}>
              {l}
            </option>
          ),
      )}
    </select>
  );
  return (
    <Card>
      <CardHeader
        title="Evidence rules"
        description="The highest skill level each type of evidence can establish. External platforms are capped low unless verified, so activity alone is never treated as expertise."
      />
      <QueryState query={rules}>
        {(list) => (
          <Table caption="Evidence rules">
            <thead>
              <tr>
                <Th>Evidence type</Th>
                <Th>Max level when unverified</Th>
                <Th>Max level when verified</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <Td className="font-medium">{r.source_label}</Td>
                  <Td>{select(r, "max_level_unverified")}</Td>
                  <Td>{select(r, "max_level_verified")}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </QueryState>
      {update.error ? (
        <CardBody>
          <FormError message={errorMessage(update.error)} />
        </CardBody>
      ) : null}
    </Card>
  );
}

function Rubrics() {
  const queryClient = useQueryClient();
  const rubrics = useQuery({
    queryKey: ["rubrics"],
    queryFn: async () => unwrap(await api.GET("/api/v1/assessments/rubrics/")),
  });
  const [name, setName] = useState("");
  const [kind, setKind] = useState("technical");
  const [criteria, setCriteria] = useState([{ name: "", max_score: 10 }]);
  const create = useMutation({
    meta: { toast: "Rubric created" },
    mutationFn: () =>
      post("/api/v1/assessments/rubrics/", {
        name,
        kind,
        criteria: criteria.filter((c) => c.name).map((c, i) => ({ ...c, order: i, description: "" })),
      }),
    onSuccess: () => {
      setName("");
      setCriteria([{ name: "", max_score: 10 }]);
      queryClient.invalidateQueries({ queryKey: ["rubrics"] });
    },
  });
  return (
    <Card>
      <CardHeader title="Assessment rubrics" />
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <QueryState query={rubrics}>
          {(list) => (
            <ul className="flex flex-col gap-3 text-sm">
              {list.map((r) => (
                <li key={r.id}>
                  <span className="font-medium">{r.name}</span>{" "}
                  <span className="text-muted capitalize">· {r.kind}</span>
                  <span className="block text-xs text-muted">
                    {r.criteria.map((c) => `${c.name} (/${c.max_score})`).join(" · ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <TextField label="Rubric name" value={name} onChange={(e) => setName(e.target.value)} required />
          <SelectField label="Type" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="technical">Technical</option>
            <option value="aptitude">Aptitude</option>
            <option value="communication">Communication</option>
          </SelectField>
          {criteria.map((c, i) => (
            <div key={i} className="flex items-end gap-2">
              <TextField
                label={`Criterion ${i + 1}`}
                value={c.name}
                onChange={(e) => setCriteria(criteria.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                className="flex-1"
              />
              <TextField
                label="Max"
                type="number"
                min={1}
                value={c.max_score}
                onChange={(e) =>
                  setCriteria(criteria.map((x, j) => (j === i ? { ...x, max_score: Number(e.target.value) } : x)))
                }
                className="w-20"
              />
            </div>
          ))}
          <Button
            variant="ghost"
            className="self-start"
            onClick={() => setCriteria([...criteria, { name: "", max_score: 10 }])}
          >
            Add criterion
          </Button>
          {create.error ? <FormError message={errorMessage(create.error)} /> : null}
          <Button
            type="submit"
            className="self-start"
            disabled={create.isPending || !name || !criteria.some((c) => c.name)}
          >
            Create rubric
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
