"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { SkillPicker } from "@/components/domain/skill-picker";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField, TextAreaField } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { VerificationBadge } from "@/components/ui/status";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { del, post } from "@/lib/api/request";

type Evidence = Schemas["Evidence"];

const SOURCES: { value: string; label: string; hint: string }[] = [
  { value: "project", label: "Project", hint: "Something you built. Link the repository or demo." },
  { value: "certification", label: "Certification", hint: "Course or certificate. Add the certificate ID." },
  { value: "github", label: "GitHub", hint: "Your GitHub profile or a notable repository." },
  {
    value: "leetcode",
    label: "LeetCode",
    hint: "Your profile. Counts as supporting evidence, not proof of expertise.",
  },
  { value: "codechef", label: "CodeChef", hint: "Your profile and rating." },
  { value: "codeforces", label: "Codeforces", hint: "Your profile and rating." },
  { value: "other", label: "Other", hint: "Anything else that shows a skill." },
];
const LEVELS = [
  { value: 1, label: "Beginner" },
  { value: 2, label: "Intermediate" },
  { value: 3, label: "Advanced" },
  { value: 4, label: "Expert" },
];

export function EvidenceView() {
  const [status, setStatus] = useState("");
  const query = useQuery({
    queryKey: ["evidence", "mine", status],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/evidence/", { params: { query: { status: status || undefined } } })),
  });
  return (
    <>
      <PageHeader
        title="Skills & Evidence"
        description="Add evidence of your skills and ask your mentor to verify it. Institution-recorded items (assessments, mock interviews) are verified automatically."
      />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Your evidence"
            action={
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">Status</span>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="h-8 rounded-md border border-border bg-surface px-2"
                >
                  <option value="">All</option>
                  <option value="verified">Verified</option>
                  <option value="pending">Pending</option>
                  <option value="self_reported">Self-reported</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
            }
          />
          <QueryState query={query}>
            {(page) =>
              page.results.length === 0 ? (
                <CardBody>
                  <EmptyState title="No evidence yet">Add your first project or certificate.</EmptyState>
                </CardBody>
              ) : (
                <ul className="divide-y divide-border">
                  {page.results.map((e) => (
                    <EvidenceRow key={e.id} item={e} />
                  ))}
                </ul>
              )
            }
          </QueryState>
        </Card>
        <AddEvidence />
      </div>
    </>
  );
}

function EvidenceRow({ item }: { item: Evidence }) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["evidence"] });
  const request = useMutation({
    meta: { toast: "Verification requested", toastBody: "Your mentor has been notified." },
    mutationFn: () => post(`/api/v1/evidence/${item.id}/request-verification/`),
    onSuccess: refresh,
  });
  const remove = useMutation({
    meta: { toast: "Evidence deleted" },
    mutationFn: () => del(`/api/v1/evidence/${item.id}/`),
    onSuccess: refresh,
  });
  const latest = item.verifications[0];
  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{item.title}</span>
        <Badge>{item.source_label}</Badge>
        <VerificationBadge status={item.verification_status} />
      </div>
      {item.description && <p className="mt-1 text-sm text-muted">{item.description}</p>}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {item.skill_tags.map((t) => (
          <span key={t.skill_id} className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs">
            {t.skill} · {t.level_label}
          </span>
        ))}
      </div>
      {item.source_url && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-1 block text-xs text-primary hover:underline"
        >
          {item.source_url}
        </a>
      )}
      {latest && (
        <p className="mt-2 text-xs text-muted">
          {latest.decision === "verified" ? "Verified" : "Rejected"} by {latest.reviewer} on{" "}
          {new Date(latest.created_at).toLocaleDateString()}
          {latest.comment && <> — “{latest.comment}”</>}
        </p>
      )}
      {!item.is_institutional && (
        <div className="mt-3 flex flex-wrap gap-2">
          {item.verification_status === "self_reported" && (
            <Button
              variant="secondary"
              onClick={() => request.mutate()}
              disabled={request.isPending || item.skill_tags.length === 0}
              title={item.skill_tags.length === 0 ? "Tag a skill first" : undefined}
            >
              Request verification
            </Button>
          )}
          {item.verification_status !== "verified" && item.verification_status !== "pending" && (
            <Button variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
              Delete
            </Button>
          )}
        </div>
      )}
      {request.error ? (
        <div className="mt-2">
          <FormError message={errorMessage(request.error)} />
        </div>
      ) : null}
    </li>
  );
}

function AddEvidence() {
  const queryClient = useQueryClient();
  const [source, setSource] = useState("project");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [reference, setReference] = useState("");
  const [tags, setTags] = useState<{ skill_id: number; name: string; claimed_level: number }[]>([]);
  const [requestVerification, setRequestVerification] = useState(true);
  const create = useMutation({
    meta: { toast: "Evidence added", toastBody: "Your skill profile and readiness update shortly." },
    mutationFn: () =>
      post("/api/v1/evidence/", {
        source_type: source,
        title,
        description,
        source_url: url,
        external_reference: reference,
        tags: tags.map(({ skill_id, claimed_level }) => ({ skill_id, claimed_level })),
        request_verification: requestVerification && tags.length > 0,
      }),
    onSuccess: () => {
      setTitle("");
      setDescription("");
      setUrl("");
      setReference("");
      setTags([]);
      queryClient.invalidateQueries({ queryKey: ["evidence"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
  const hint = SOURCES.find((s) => s.value === source)?.hint;

  return (
    <Card>
      <CardHeader title="Add evidence" />
      <CardBody>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <SelectField label="Type" value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </SelectField>
          {hint && <p className="-mt-1 text-xs text-muted">{hint}</p>}
          <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
          <TextAreaField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
          <TextField
            label="Link"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://"
          />
          <TextField
            label="Reference (handle, certificate ID)"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">Skills shown</legend>
            {tags.map((t, i) => (
              <div key={t.skill_id} className="flex items-center gap-2 text-sm">
                <span className="flex-1">{t.name}</span>
                <label className="sr-only" htmlFor={`lvl-${t.skill_id}`}>
                  Level for {t.name}
                </label>
                <select
                  id={`lvl-${t.skill_id}`}
                  value={t.claimed_level}
                  onChange={(e) =>
                    setTags(tags.map((x, j) => (j === i ? { ...x, claimed_level: Number(e.target.value) } : x)))
                  }
                  className="h-8 rounded-md border border-border bg-surface px-2"
                >
                  {LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  onClick={() => setTags(tags.filter((_, j) => j !== i))}
                  aria-label={`Remove ${t.name}`}
                >
                  ×
                </Button>
              </div>
            ))}
            <SkillPicker
              label="Add a skill…"
              exclude={tags.map((t) => t.skill_id)}
              onPick={(s) => setTags([...tags, { skill_id: s.id, name: s.name, claimed_level: 2 }])}
            />
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={requestVerification}
              onChange={(e) => setRequestVerification(e.target.checked)}
            />
            Ask my mentor to verify it
          </label>
          <p className="text-xs text-muted">
            Unverified evidence counts for less, and external platform activity alone cannot establish advanced levels.
          </p>
          {create.error ? <FormError message={errorMessage(create.error)} /> : null}
          <Button type="submit" disabled={!title.trim() || create.isPending}>
            Add evidence
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
