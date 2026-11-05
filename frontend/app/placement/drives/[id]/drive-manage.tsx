"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { BarList } from "@/components/charts/bar-list";
import { EvaluationView } from "@/components/domain/evaluation";
import { ExportButton } from "@/components/domain/export-button";
import { SkillPicker } from "@/components/domain/skill-picker";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField, TextAreaField } from "@/components/ui/form";
import { Meter } from "@/components/ui/meter";
import { pct } from "@/components/ui/stat";
import { errorMessage, Loading, QueryState } from "@/components/ui/states";
import { DriveStatusBadge, EligibilityBadge, RegistrationBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { del, get, post, upload } from "@/lib/api/request";
import type { Evaluation, Funnel, JDState, MatchList, SupplyDemand } from "@/lib/api/types";

type Drive = Schemas["Drive"];
type Tab = "setup" | "jd" | "matching" | "supply" | "funnel";

const LEVELS = ["", "Beginner", "Intermediate", "Advanced", "Expert"];
const NEXT_STATUS: Record<string, { status: string; label: string }[]> = {
  draft: [{ status: "published", label: "Publish (opens registration)" }],
  published: [{ status: "registration_closed", label: "Close registration" }],
  registration_closed: [{ status: "shortlisting", label: "Start shortlisting" }],
  shortlisting: [{ status: "completed", label: "Mark completed" }],
};

export function DriveManage({ id }: { id: number }) {
  const [tab, setTab] = useState<Tab>("setup");
  const drive = useQuery({
    queryKey: ["drive", id],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/{id}/", { params: { path: { id } } })),
  });
  return (
    <QueryState query={drive}>
      {(d) => (
        <>
          <PageHeader
            title={`${d.company.name} — ${d.role_title}`}
            description={[d.location, d.compensation, d.drive_date && `Drive on ${d.drive_date}`]
              .filter(Boolean)
              .join(" · ")}
            actions={<DriveStatusBadge status={d.status ?? ""} label={d.status_label} />}
          />
          <Tabs
            label="Drive sections"
            value={tab}
            onChange={setTab}
            tabs={[
              { value: "setup", label: "Requirements & eligibility" },
              { value: "jd", label: "Job description" },
              { value: "matching", label: "Matching & shortlist" },
              { value: "supply", label: "Supply vs demand" },
              { value: "funnel", label: "Funnel" },
            ]}
          />
          {tab === "setup" && <Setup drive={d} />}
          {tab === "jd" && <JDPanel drive={d} />}
          {tab === "matching" && <Matching drive={d} />}
          {tab === "supply" && <Supply drive={d} />}
          {tab === "funnel" && <FunnelPanel drive={d} />}
        </>
      )}
    </QueryState>
  );
}

function useDriveRefresh(id: number) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["drive", id] });
    queryClient.invalidateQueries({ queryKey: ["drives"] });
  };
}

function Setup({ drive }: { drive: Drive }) {
  const refresh = useDriveRefresh(drive.id);
  const editable = drive.status === "draft" || drive.status === "published";
  const transition = useMutation({
    meta: { toast: (v: never) => `Drive moved to ${(v as string).replace(/_/g, " ")}` },
    mutationFn: (status: string) => post(`/api/v1/drives/${drive.id}/transition/`, { status }),
    onSuccess: refresh,
  });
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <Requirements drive={drive} editable={editable} />
      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader
            title="Lifecycle"
            description="Publishing runs eligibility and matching for every student and notifies them."
          />
          <CardBody className="flex flex-col gap-3 text-sm">
            <p>
              Registration: {drive.registration_open ? <Badge tone="success">Open</Badge> : <Badge>Closed</Badge>}
              {drive.registration_closes_at && (
                <span className="ml-2 text-muted">
                  closes {new Date(drive.registration_closes_at).toLocaleString()}
                </span>
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              {(NEXT_STATUS[drive.status ?? ""] ?? []).map((n) => (
                <Button key={n.status} onClick={() => transition.mutate(n.status)} disabled={transition.isPending}>
                  {n.label}
                </Button>
              ))}
              {drive.status !== "completed" && drive.status !== "cancelled" && (
                <Button variant="ghost" onClick={() => transition.mutate("cancelled")} disabled={transition.isPending}>
                  Cancel drive
                </Button>
              )}
            </div>
            {transition.error ? <FormError message={errorMessage(transition.error)} /> : null}
          </CardBody>
        </Card>
        <EligibilityRules drive={drive} editable={editable} />
        <RoleTemplate drive={drive} editable={editable} />
      </div>
    </div>
  );
}

function Requirements({ drive, editable }: { drive: Drive; editable: boolean }) {
  const refresh = useDriveRefresh(drive.id);
  const [pending, setPending] = useState<{ id: number; name: string } | null>(null);
  const [level, setLevel] = useState(2);
  const [weight, setWeight] = useState(2);
  const [mandatory, setMandatory] = useState(false);
  const add = useMutation({
    meta: { toast: "Requirement added" },
    mutationFn: () =>
      post(`/api/v1/drives/${drive.id}/requirements/`, {
        skill_id: pending!.id,
        required_level: level,
        weight,
        is_mandatory: mandatory,
      }),
    onSuccess: () => {
      setPending(null);
      refresh();
    },
  });
  const remove = useMutation({
    meta: { toast: "Requirement removed" },
    mutationFn: (skillId: number) => del(`/api/v1/drives/${drive.id}/requirements/${skillId}/`),
    onSuccess: refresh,
  });
  return (
    <Card>
      <CardHeader
        title="Skill requirements"
        description="Mapped to the institutional taxonomy, so 'Frontend Framework' also matches React, Vue, etc."
      />
      {drive.requirements.length === 0 ? (
        <CardBody>
          <EmptyState title="No requirements yet">Paste the JD, apply a role template, or add skills below.</EmptyState>
        </CardBody>
      ) : (
        <Table caption="Requirements">
          <thead>
            <tr>
              <Th>Skill</Th>
              <Th>Required level</Th>
              <Th>Weight</Th>
              <Th>Source</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {drive.requirements.map((r) => (
              <tr key={r.id}>
                <Td>
                  <span className="font-medium">{r.skill}</span>
                  {r.is_mandatory && <Badge tone="primary">Mandatory</Badge>}
                </Td>
                <Td>{r.level_label}</Td>
                <Td className="tabular-nums">{r.weight}</Td>
                <Td className="text-xs text-muted">{(r.source ?? "").replace(/_/g, " ")}</Td>
                <Td>
                  {editable && (
                    <Button variant="ghost" onClick={() => remove.mutate(r.skill_id)} aria-label={`Remove ${r.skill}`}>
                      Remove
                    </Button>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {editable && (
        <CardBody className="flex flex-col gap-3 border-t border-border">
          {pending ? (
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                add.mutate();
              }}
            >
              <span className="text-sm font-medium">{pending.name}</span>
              <SelectField label="Level" value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                {[1, 2, 3, 4].map((l) => (
                  <option key={l} value={l}>
                    {LEVELS[l]}
                  </option>
                ))}
              </SelectField>
              <TextField
                label="Weight (1–10)"
                type="number"
                min={1}
                max={10}
                value={weight}
                onChange={(e) => setWeight(Number(e.target.value))}
                className="w-28"
              />
              <label className="flex items-center gap-2 pb-2 text-sm">
                <input type="checkbox" checked={mandatory} onChange={(e) => setMandatory(e.target.checked)} />
                Mandatory
              </label>
              <Button type="submit" disabled={add.isPending}>
                Add requirement
              </Button>
              <Button variant="ghost" onClick={() => setPending(null)}>
                Cancel
              </Button>
            </form>
          ) : (
            <SkillPicker
              label="Add a required skill…"
              exclude={drive.requirements.map((r) => r.skill_id)}
              onPick={(s) => setPending({ id: s.id, name: s.name })}
            />
          )}
          {add.error ? <FormError message={errorMessage(add.error)} /> : null}
        </CardBody>
      )}
    </Card>
  );
}

const RULE_LABELS: Record<string, string> = {
  min_cgpa: "Minimum CGPA",
  max_active_backlogs: "Maximum active backlogs",
  department_in: "Departments (codes, comma-separated)",
  graduation_year_in: "Graduation years (comma-separated)",
};

function EligibilityRules({ drive, editable }: { drive: Drive; editable: boolean }) {
  const refresh = useDriveRefresh(drive.id);
  const [type, setType] = useState("min_cgpa");
  const [value, setValue] = useState("");
  const parse = () => {
    if (type === "min_cgpa") return Number(value);
    if (type === "max_active_backlogs") return parseInt(value, 10);
    if (type === "graduation_year_in")
      return value
        .split(",")
        .map((v) => parseInt(v.trim(), 10))
        .filter((v) => !Number.isNaN(v));
    return value
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
  };
  const save = useMutation({
    meta: { toast: "Eligibility rule saved" },
    mutationFn: () => post(`/api/v1/drives/${drive.id}/eligibility-rules/`, { rule_type: type, value: parse() }),
    onSuccess: () => {
      setValue("");
      refresh();
    },
  });
  const remove = useMutation({
    meta: { toast: "Eligibility rule removed" },
    mutationFn: (t: string) => del(`/api/v1/drives/${drive.id}/eligibility-rules/${t}/`),
    onSuccess: refresh,
  });
  return (
    <Card>
      <CardHeader title="Eligibility criteria" description="Hard criteria only. Never mixed into readiness." />
      <CardBody className="flex flex-col gap-3 text-sm">
        {drive.eligibility_rules.length === 0 ? (
          <p className="text-muted">No criteria: every student is eligible.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {drive.eligibility_rules.map((r) => (
              <li key={r.rule_type} className="flex items-center justify-between gap-2">
                <span>
                  <span className="text-muted">{r.label}:</span>{" "}
                  {Array.isArray(r.value) ? (r.value as unknown[]).join(", ") : String(r.value)}
                </span>
                {editable && (
                  <Button variant="ghost" onClick={() => remove.mutate(r.rule_type)}>
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {editable && (
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <SelectField label="Criterion" value={type} onChange={(e) => setType(e.target.value)}>
              {Object.entries(RULE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              className="w-40"
            />
            <Button type="submit" variant="secondary" disabled={save.isPending || !value}>
              Set
            </Button>
          </form>
        )}
        {save.error ? <FormError message={errorMessage(save.error)} /> : null}
      </CardBody>
    </Card>
  );
}

function RoleTemplate({ drive, editable }: { drive: Drive; editable: boolean }) {
  const refresh = useDriveRefresh(drive.id);
  const roles = useQuery({
    queryKey: ["taxonomy", "roles"],
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/roles/")).results,
  });
  const [role, setRole] = useState("");
  const apply = useMutation({
    meta: { toast: "Role requirements applied" },
    mutationFn: () => post(`/api/v1/drives/${drive.id}/apply-role/`, { role_id: Number(role) }),
    onSuccess: refresh,
  });
  if (!editable) return null;
  return (
    <Card>
      <CardHeader title="Role template" description="Add a target role's skills (existing requirements are kept)." />
      <CardBody>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            apply.mutate();
          }}
        >
          <SelectField label="Target role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">Choose…</option>
            {roles.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </SelectField>
          <Button type="submit" variant="secondary" disabled={!role || apply.isPending}>
            Apply
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

const JD_ACCEPT =
  ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";
const JD_MAX_BYTES = 5 * 1024 * 1024;

/** Client-side pre-check; the server re-validates the file by its content. */
function jdFileProblem(file: File): string | null {
  if (file.size > JD_MAX_BYTES) return "The JD file must be 5 MB or smaller.";
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) return "Upload the JD as a PDF, Word (.docx) or .txt file.";
  return null;
}

function JDPanel({ drive }: { drive: Drive }) {
  const queryClient = useQueryClient();
  const jd = useQuery({
    queryKey: ["drive", drive.id, "jd"],
    queryFn: () => get<JDState>(`/api/v1/drives/${drive.id}/jd/`),
    refetchInterval: (q) => (q.state.data?.status === "processing" ? 1500 : false),
  });
  const [edited, setText] = useState<string | null>(null);
  const text = edited ?? jd.data?.text ?? "";
  const submit = useMutation({
    meta: { toast: "JD submitted", toastBody: "Processing runs in the background." },
    mutationFn: () => post(`/api/v1/drives/${drive.id}/jd/`, { text }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["drive", drive.id] }),
  });
  const fileInput = useRef<HTMLInputElement>(null);
  const sendFile = useMutation({
    meta: { toast: "JD file read", toastBody: "Its text is shown on the left; processing runs in the background." },
    mutationFn: (file: File) => {
      const problem = jdFileProblem(file);
      if (problem) throw new Error(problem);
      const form = new FormData();
      form.append("file", file);
      return upload<JDState>(`/api/v1/drives/${drive.id}/jd/`, form);
    },
    onSuccess: () => {
      setText(null);
      return queryClient.invalidateQueries({ queryKey: ["drive", drive.id] });
    },
  });
  const busy = submit.isPending || sendFile.isPending;
  const editable = drive.status === "draft" || drive.status === "published";
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <CardHeader
          title="Paste or upload the company's job description"
          description="Processing is deterministic: it matches the text against the institutional skill taxonomy and common eligibility phrasing. No AI is involved, and you review everything before it is applied."
        />
        <CardBody className="flex flex-col gap-3">
          <TextAreaField
            label="Job description"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={16}
            disabled={!editable}
          />
          {submit.error ? <FormError message={errorMessage(submit.error)} /> : null}
          {sendFile.error ? <FormError message={errorMessage(sendFile.error)} /> : null}
          {editable && (
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => submit.mutate()} disabled={!text.trim() || busy}>
                Process JD
              </Button>
              <input
                ref={fileInput}
                type="file"
                accept={JD_ACCEPT}
                className="sr-only"
                aria-label="JD file (PDF, Word or text)"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) sendFile.mutate(file);
                  e.target.value = "";
                }}
              />
              <Button variant="secondary" onClick={() => fileInput.current?.click()} disabled={busy}>
                <FileUp aria-hidden="true" className="size-4" />
                {sendFile.isPending ? "Reading file…" : "Upload PDF, Word or .txt"}
              </Button>
              <p className="text-xs text-muted">Scanned PDFs have no text to read; paste the text instead.</p>
            </div>
          )}
        </CardBody>
      </Card>
      <QueryState query={jd}>
        {(state) =>
          state.status === "processing" ? (
            <Card>
              <CardBody>
                <Loading label="Processing the JD…" />
              </CardBody>
            </Card>
          ) : state.status === "ready" || state.status === "applied" ? (
            <ExtractionReview drive={drive} state={state} editable={editable} />
          ) : state.status === "failed" ? (
            <Card>
              <CardBody>
                <FormError message="Processing failed. Check the text and try again." />
              </CardBody>
            </Card>
          ) : (
            <Card>
              <CardBody>
                <EmptyState title="No JD processed yet" />
              </CardBody>
            </Card>
          )
        }
      </QueryState>
    </div>
  );
}

function ExtractionReview({ drive, state, editable }: { drive: Drive; state: JDState; editable: boolean }) {
  const queryClient = useQueryClient();
  const skills = state.extraction.skills ?? [];
  const rules = state.extraction.eligibility ?? [];
  const [chosen, setChosen] = useState<
    Record<number, { required_level: number; weight: number; is_mandatory: boolean; on: boolean }>
  >(() =>
    Object.fromEntries(
      skills.map((s) => [
        s.skill_id,
        { required_level: s.required_level, weight: s.weight, is_mandatory: s.is_mandatory, on: true },
      ]),
    ),
  );
  const [chosenRules, setChosenRules] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(rules.map((r) => [r.rule_type, true])),
  );
  const apply = useMutation({
    meta: { toast: "Requirements saved from the JD" },
    mutationFn: () =>
      post(`/api/v1/drives/${drive.id}/jd/apply/`, {
        skills: skills
          .filter((s) => chosen[s.skill_id]?.on)
          .map((s) => ({
            skill_id: s.skill_id,
            required_level: chosen[s.skill_id].required_level,
            weight: chosen[s.skill_id].weight,
            is_mandatory: chosen[s.skill_id].is_mandatory,
          })),
        rules: rules.filter((r) => chosenRules[r.rule_type]).map((r) => ({ rule_type: r.rule_type, value: r.value })),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drive", drive.id] });
    },
  });
  const set = (id: number, patch: Partial<(typeof chosen)[number]>) =>
    setChosen({ ...chosen, [id]: { ...chosen[id], ...patch } });
  return (
    <Card>
      <CardHeader
        title="Review extracted requirements"
        description={
          state.status === "applied"
            ? "Applied. You can adjust and apply again."
            : "Untick anything that is wrong, adjust levels and weights, then apply."
        }
      />
      <CardBody className="flex flex-col gap-4 text-sm">
        {skills.length === 0 ? (
          <p className="text-muted">
            No taxonomy skills were found in the text. Add requirements manually or extend the taxonomy.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {skills.map((s) => (
              <li key={s.skill_id} className="rounded-md border border-border p-2.5">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 font-medium">
                    <input
                      type="checkbox"
                      checked={chosen[s.skill_id]?.on}
                      onChange={(e) => set(s.skill_id, { on: e.target.checked })}
                    />
                    {s.skill}
                  </label>
                  <select
                    aria-label={`Level for ${s.skill}`}
                    value={chosen[s.skill_id]?.required_level}
                    onChange={(e) => set(s.skill_id, { required_level: Number(e.target.value) })}
                    className="h-8 rounded-md border border-border bg-surface px-2"
                  >
                    {[1, 2, 3, 4].map((l) => (
                      <option key={l} value={l}>
                        {LEVELS[l]}
                      </option>
                    ))}
                  </select>
                  <label className="flex items-center gap-1">
                    Weight
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={chosen[s.skill_id]?.weight}
                      onChange={(e) => set(s.skill_id, { weight: Number(e.target.value) })}
                      className="h-8 w-16 rounded-md border border-border bg-surface px-2"
                    />
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={chosen[s.skill_id]?.is_mandatory}
                      onChange={(e) => set(s.skill_id, { is_mandatory: e.target.checked })}
                    />
                    Mandatory
                  </label>
                </div>
                <p className="mt-1 text-xs text-muted">
                  Found “{s.matched_text}” in: {s.evidence}
                </p>
              </li>
            ))}
          </ul>
        )}
        <div>
          <p className="mb-1 font-medium">Eligibility found in the JD</p>
          {rules.length === 0 ? (
            <p className="text-muted">None detected.</p>
          ) : (
            rules.map((r) => (
              <label key={r.rule_type} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={chosenRules[r.rule_type]}
                  onChange={(e) => setChosenRules({ ...chosenRules, [r.rule_type]: e.target.checked })}
                />
                {r.label}
              </label>
            ))
          )}
        </div>
        {apply.error ? <FormError message={errorMessage(apply.error)} /> : null}
        {editable && (
          <Button onClick={() => apply.mutate()} disabled={apply.isPending} className="self-start">
            Apply to drive
          </Button>
        )}
      </CardBody>
    </Card>
  );
}

function Matching({ drive }: { drive: Drive }) {
  const queryClient = useQueryClient();
  const [eligible, setEligible] = useState("");
  const [registered, setRegistered] = useState(false);
  const [minCompat, setMinCompat] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const params = new URLSearchParams({
    ...(eligible && { eligible }),
    ...(registered && { registered: "true" }),
    ...(minCompat && { min_compatibility: minCompat }),
    ...(q && { q }),
  });
  const results = useQuery({
    queryKey: ["drive", drive.id, "match", params.toString()],
    queryFn: () => get<MatchList>(`/api/v1/drives/${drive.id}/match/?${params}`),
  });
  const jobs = useQuery({
    queryKey: ["drive", drive.id, "jobs"],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/{id}/jobs/", { params: { path: { id: drive.id } } })),
    refetchInterval: (query) =>
      query.state.data?.some((j) => j.status === "queued" || j.status === "running") ? 1500 : false,
  });
  const running = jobs.data?.some((j) => j.status === "queued" || j.status === "running");
  const wasRunning = useRef(false);
  useEffect(() => {
    // Refresh results once when a matching run we were watching finishes.
    if (running) wasRunning.current = true;
    else if (wasRunning.current) {
      wasRunning.current = false;
      queryClient.invalidateQueries({ queryKey: ["drive", drive.id] });
    }
  }, [running, drive.id, queryClient]);
  const run = useMutation({
    meta: { toast: "Matching started", toastBody: "Results refresh when the job finishes." },
    mutationFn: () => post(`/api/v1/drives/${drive.id}/match/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["drive", drive.id, "jobs"] }),
  });
  const decide = useMutation({
    meta: { toast: (v: never) => `Marked ${(v as { status: string }).status.replace(/_/g, " ")}` },
    mutationFn: ({ reg, status }: { reg: number; status: string }) =>
      post(`/api/v1/drives/${drive.id}/registrations/${reg}/decide/`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["drive", drive.id, "match"] }),
  });
  const canDecide = drive.status === "registration_closed" || drive.status === "shortlisting";
  const job = jobs.data?.[0];

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader
          title="Run matching"
          description="Evaluates eligibility, skill compatibility, drive readiness and gaps for every student, as a background job."
          action={
            <Button onClick={() => run.mutate()} disabled={run.isPending || running || drive.requirements.length === 0}>
              {running ? "Running…" : "Run matching"}
            </Button>
          }
        />
        {job && (
          <CardBody className="flex flex-col gap-2 text-sm">
            <p>
              Last job: <span className="capitalize">{job.status}</span>
              {job.duration_seconds != null && ` in ${job.duration_seconds.toFixed(1)}s`} · {job.processed}/{job.total}{" "}
              students{job.finished_at && ` · finished ${new Date(job.finished_at).toLocaleString()}`}
            </p>
            {running && (
              <Meter value={job.total ? (100 * (job.processed ?? 0)) / job.total : 0} label="Matching progress" />
            )}
            {job.error && <FormError message={job.error} />}
          </CardBody>
        )}
      </Card>
      <QueryState query={results}>
        {(m) => (
          <Card>
            <CardHeader
              title="Students"
              description={`${m.summary.evaluated} evaluated · ${m.summary.eligible} eligible · ${m.summary.high_match} with ≥70% skill match · ${m.summary.registered} registered · average match ${pct(m.summary.average_compatibility)}`}
            />
            <div className="flex flex-wrap items-end gap-3 border-b border-border px-5 py-3">
              <SelectField label="Eligibility" value={eligible} onChange={(e) => setEligible(e.target.value)}>
                <option value="">All</option>
                <option value="true">Eligible</option>
                <option value="false">Not eligible</option>
              </SelectField>
              <TextField
                label="Min skill match %"
                type="number"
                min={0}
                max={100}
                value={minCompat}
                onChange={(e) => setMinCompat(e.target.value)}
                className="w-36"
              />
              <TextField label="Search" value={q} onChange={(e) => setQ(e.target.value)} className="w-48" />
              <label className="flex items-center gap-2 pb-2 text-sm">
                <input type="checkbox" checked={registered} onChange={(e) => setRegistered(e.target.checked)} />
                Registered only
              </label>
              <div className="ml-auto">
                <ExportButton
                  path={`/api/v1/drives/${drive.id}/export/?${params}`}
                  filename={`${drive.company.name}-${drive.role_title}`}
                />
              </div>
            </div>
            {m.results.length === 0 ? (
              <CardBody>
                <EmptyState
                  title={m.last_matched_at ? "No students match these filters" : "Matching has not run yet"}
                />
              </CardBody>
            ) : (
              <Table caption="Matching results">
                <thead>
                  <tr>
                    <Th>Student</Th>
                    <Th>Eligibility</Th>
                    <Th>Skill match</Th>
                    <Th>Readiness</Th>
                    <Th>Registration</Th>
                    {canDecide && <Th>Decision</Th>}
                  </tr>
                </thead>
                <tbody>
                  {m.results.map((r) => (
                    <tr key={r.student_id} className={selected === r.student_id ? "bg-primary-soft/40" : undefined}>
                      <Td>
                        <button
                          type="button"
                          className="text-left font-medium hover:underline"
                          onClick={() => setSelected(selected === r.student_id ? null : r.student_id)}
                        >
                          {r.name}
                        </button>
                        <span className="block text-xs text-muted">
                          {r.roll_number} · {r.department} · CGPA {r.cgpa}
                        </span>
                      </Td>
                      <Td>
                        <EligibilityBadge eligible={r.eligible} />
                        {r.failed_criteria.length > 0 && (
                          <span className="block text-xs text-muted">{r.failed_criteria.join("; ")}</span>
                        )}
                      </Td>
                      <Td className="tabular-nums">{r.compatibility.toFixed(0)}%</Td>
                      <Td className="tabular-nums">{pct(r.readiness)}</Td>
                      <Td>
                        <RegistrationBadge status={r.registration_status} />
                      </Td>
                      {canDecide && (
                        <Td>
                          {r.registration_id && r.registration_status !== "withdrawn" && (
                            <select
                              aria-label={`Decision for ${r.name}`}
                              value=""
                              disabled={decide.isPending}
                              onChange={(e) =>
                                e.target.value && decide.mutate({ reg: r.registration_id!, status: e.target.value })
                              }
                              className="h-8 rounded-md border border-border bg-surface px-2 text-sm"
                            >
                              <option value="">Set…</option>
                              <option value="shortlisted">Shortlist</option>
                              <option value="not_shortlisted">Not shortlisted</option>
                              <option value="selected">Selected</option>
                              <option value="not_selected">Not selected</option>
                            </select>
                          )}
                        </Td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            {decide.error ? (
              <CardBody>
                <FormError message={errorMessage(decide.error)} />
              </CardBody>
            ) : null}
          </Card>
        )}
      </QueryState>
      {selected && <StudentEvaluation driveId={drive.id} studentId={selected} />}
    </div>
  );
}

function StudentEvaluation({ driveId, studentId }: { driveId: number; studentId: number }) {
  const ev = useQuery({
    queryKey: ["drive", driveId, "student", studentId],
    queryFn: () => get<Evaluation>(`/api/v1/drives/${driveId}/students/${studentId}/`),
  });
  return (
    <section aria-label="Student evaluation">
      <h2 className="mb-3 text-sm font-semibold">Student evaluation</h2>
      <QueryState query={ev}>{(e) => <EvaluationView evaluation={e} />}</QueryState>
    </section>
  );
}

function Supply({ drive }: { drive: Drive }) {
  const [population, setPopulation] = useState<"all" | "eligible">("all");
  const report = useQuery({
    queryKey: ["reports", "supply", drive.id, population],
    queryFn: () => get<SupplyDemand>(`/api/v1/reports/drives/${drive.id}/supply-demand/?population=${population}`),
  });
  return (
    <Card>
      <CardHeader
        title="Skill supply vs drive demand"
        description="For each requirement: share of students whose profile meets the required level. Lowest supply first: that is what training should target."
        action={
          <SelectField
            label="Population"
            value={population}
            onChange={(e) => setPopulation(e.target.value as "all" | "eligible")}
          >
            <option value="all">All students</option>
            <option value="eligible">Eligible students</option>
          </SelectField>
        }
      />
      <QueryState query={report}>
        {(r) =>
          r.requirements.length === 0 ? (
            <CardBody>
              <EmptyState title="No requirements" />
            </CardBody>
          ) : (
            <CardBody className="flex flex-col gap-5">
              <BarList
                title="Students meeting each requirement"
                rows={r.requirements.map((x) => ({
                  key: x.skill_id,
                  label: `${x.skill} (${x.required_level}+)${x.is_mandatory ? " · mandatory" : ""}`,
                  value: x.supply_percent,
                  cluster: x.cluster ?? null,
                  note: `${x.verified_supply_percent}% with verified evidence · ${x.any_evidence_percent}% have any evidence · ${x.shortfall_students} students short · ${x.demand_share}% of the drive's weight`,
                }))}
              />
              <p className="text-xs text-muted">
                Population: {r.students} students. Computed from current skill claims.
              </p>
            </CardBody>
          )
        }
      </QueryState>
    </Card>
  );
}

function FunnelPanel({ drive }: { drive: Drive }) {
  const funnel = useQuery({
    queryKey: ["reports", "funnel", drive.id],
    queryFn: () => get<Funnel>(`/api/v1/reports/drives/${drive.id}/funnel/`),
  });
  return (
    <Card>
      <CardHeader title="Drive funnel" description="Evaluated → eligible → registered → shortlisted → selected." />
      <CardBody>
        <QueryState query={funnel}>
          {(f) => {
            const top = Math.max(1, f.stages[0]?.count ?? 1);
            return (
              <BarList
                title="Drive funnel"
                max={top}
                rows={f.stages.map((s) => ({ key: s.stage, label: s.stage, value: s.count, display: String(s.count) }))}
              />
            );
          }}
        </QueryState>
      </CardBody>
    </Card>
  );
}
