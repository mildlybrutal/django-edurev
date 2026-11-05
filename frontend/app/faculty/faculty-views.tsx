"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { CertificateViewButton } from "@/components/domain/certificate";
import { ExportButton } from "@/components/domain/export-button";
import { SkillPicker } from "@/components/domain/skill-picker";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField, TextAreaField } from "@/components/ui/form";
import { pct, StatCard, StatGrid } from "@/components/ui/stat";
import { errorMessage, QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { get, post, qs } from "@/lib/api/request";
import type { FacultyDashboard, StudentSummary } from "@/lib/api/types";

export function FacultyDashboardView() {
  const query = useQuery({
    queryKey: ["dashboard", "faculty"],
    queryFn: () => get<FacultyDashboard>("/api/v1/dashboard/faculty/"),
  });
  return (
    <QueryState query={query}>
      {(d) => (
        <>
          <PageHeader title="Faculty dashboard" description="Your mentees and the evidence waiting for your review." />
          <StatGrid>
            <StatCard label="Mentees" value={d.mentees} />
            <StatCard
              label="Pending verifications"
              value={d.pending_verifications}
              hint={
                <Link className="text-primary" href="/faculty/verification">
                  Open queue
                </Link>
              }
            />
          </StatGrid>
          <MenteeTable rows={d.students} />
        </>
      )}
    </QueryState>
  );
}

const BANDS = [
  { value: "", label: "All readiness" },
  { value: "0-40", label: "Below 40%" },
  { value: "40-60", label: "40–60%" },
  { value: "60-80", label: "60–80%" },
  { value: "80-100", label: "80–100%" },
  { value: "none", label: "Not computed" },
];

function inBand(readiness: number | null, band: string) {
  if (!band) return true;
  if (band === "none") return readiness === null;
  const [low, high] = band.split("-").map(Number);
  return readiness !== null && readiness >= low && readiness < (high >= 100 ? 101 : high);
}

export function MenteeTable({ rows, action }: { rows: StudentSummary[]; action?: ReactNode }) {
  return (
    <Card>
      <CardHeader
        title="Mentees"
        description="Lowest readiness first, so you know who to check in with. Eligibility for each drive is shown separately on the student page."
        action={action}
      />
      {rows.length === 0 ? (
        <div className="p-5">
          <EmptyState title="No mentees match" />
        </div>
      ) : (
        <Table caption="Mentees">
          <thead>
            <tr>
              <Th>Student</Th>
              <Th>Academics</Th>
              <Th>Readiness</Th>
              <Th>Evidence</Th>
              <Th>Drives</Th>
              <Th>Plan</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <Td>
                  <Link className="font-medium hover:underline" href={`/faculty/students/${s.id}`}>
                    {s.name}
                  </Link>
                  <span className="block text-xs text-muted">
                    {s.roll_number} · {s.department} · {s.graduation_year}
                  </span>
                </Td>
                <Td className="tabular-nums">
                  CGPA {s.cgpa.toFixed(2)}
                  <span className="block text-xs text-muted">
                    {s.active_backlogs} backlog(s){s.academic_record_verified ? "" : " · self-declared"}
                  </span>
                </Td>
                <Td className="tabular-nums">{pct(s.readiness)}</Td>
                <Td>
                  <span className="tabular-nums">
                    {s.evidence_verified}/{s.evidence_total} verified
                  </span>
                  {s.evidence_pending > 0 && (
                    <span className="mt-0.5 block">
                      <Badge tone="warning">{s.evidence_pending} pending</Badge>
                    </span>
                  )}
                </Td>
                <Td className="tabular-nums">
                  {s.registrations} registered
                  <span className="block text-xs text-muted">{s.eligible_drives} eligible (active)</span>
                </Td>
                <Td className="tabular-nums">{s.plan_total ? `${s.plan_done}/${s.plan_total} tasks` : "No plan"}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

export function MenteesView() {
  const query = useQuery({
    queryKey: ["dashboard", "faculty"],
    queryFn: () => get<FacultyDashboard>("/api/v1/dashboard/faculty/"),
  });
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [band, setBand] = useState("");
  const rows = useMemo(() => query.data?.students ?? [], [query.data]);
  const departments = useMemo(() => [...new Set(rows.map((r) => r.department))].sort(), [rows]);
  const needle = q.trim().toLowerCase();
  const filtered = rows.filter(
    (r) =>
      (!needle || r.name.toLowerCase().includes(needle) || r.roll_number.includes(needle)) &&
      (!department || r.department === department) &&
      inBand(r.readiness, band),
  );
  return (
    <>
      <PageHeader title="My Students" description="Each mentee's academics, readiness, evidence, drives and plan." />
      <div className="flex flex-wrap items-end gap-3">
        <TextField label="Search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or reg. no." />
        <SelectField label="Department" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </SelectField>
        <SelectField label="Readiness" value={band} onChange={(e) => setBand(e.target.value)}>
          {BANDS.map((b) => (
            <option key={b.value} value={b.value}>
              {b.label}
            </option>
          ))}
        </SelectField>
      </div>
      <QueryState query={query}>
        {() => (
          <MenteeTable
            rows={filtered}
            action={
              <ExportButton
                path={`/api/v1/students/export/${qs({ q: needle, department, band })}`}
                filename="mentees"
              />
            }
          />
        )}
      </QueryState>
    </>
  );
}

export function VerificationQueue() {
  const query = useQuery({
    queryKey: ["verification", "queue"],
    queryFn: async () => unwrap(await api.GET("/api/v1/verification/queue/")),
  });
  return (
    <>
      <PageHeader
        title="Verification Queue"
        description="Evidence your mentees asked you to verify, oldest first. Verified evidence counts fully toward skill levels."
      />
      <QueryState query={query}>
        {(items) =>
          items.length === 0 ? (
            <EmptyState title="Nothing to review">You&apos;re up to date.</EmptyState>
          ) : (
            <div className="flex flex-col gap-4">
              {items.map((e) => (
                <ReviewCard key={e.id} item={e} />
              ))}
            </div>
          )
        }
      </QueryState>
    </>
  );
}

function ReviewCard({ item }: { item: Schemas["Evidence"] }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const decide = useMutation({
    meta: { toast: (v: never) => ((v as string) === "verified" ? "Evidence verified" : "Evidence rejected") },
    mutationFn: (decision: "verified" | "rejected") =>
      post(`/api/v1/verification/${item.id}/decide/`, { decision, comment }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["verification"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  return (
    <Card>
      <CardHeader
        title={item.title}
        description={`${item.student_name} · ${item.source_label} · submitted ${new Date(item.submitted_at).toLocaleDateString()}`}
      />
      <CardBody className="flex flex-col gap-3 text-sm">
        {item.description && <p>{item.description}</p>}
        {item.source_url && (
          <a href={item.source_url} target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
            {item.source_url}
          </a>
        )}
        {item.external_reference && <p className="text-muted">Reference: {item.external_reference}</p>}
        {item.certificate ? (
          <div className="flex items-center gap-2">
            <CertificateViewButton item={item} />
            <span className="text-xs text-muted">{item.certificate.name}</span>
          </div>
        ) : (
          item.source_type === "certification" && <p className="text-muted">No certificate file attached.</p>
        )}
        <div className="flex flex-wrap gap-1.5">
          {item.skill_tags.map((t) => (
            <Badge key={t.skill_id}>
              {t.skill} · claims {t.level_label}
            </Badge>
          ))}
        </div>
        <TextAreaField
          label="Comment to the student"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Required when rejecting"
        />
        {decide.error ? <FormError message={errorMessage(decide.error)} /> : null}
        <div className="flex gap-2">
          <Button onClick={() => decide.mutate("verified")} disabled={decide.isPending}>
            Verify
          </Button>
          <Button
            variant="danger"
            onClick={() => decide.mutate("rejected")}
            disabled={decide.isPending || !comment.trim()}
          >
            Reject
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

/** Record rubric assessments and mock interviews for mentees (placement cell can use it for anyone). */
export function RecordAssessments() {
  const students = useQuery({
    queryKey: ["students", "assessable"],
    queryFn: async () => unwrap(await api.GET("/api/v1/students/")).results,
  });
  return (
    <>
      <PageHeader
        title="Assessments & Mock Interviews"
        description="Recorded results become verified institutional evidence and update the student's readiness."
      />
      <QueryState query={students}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No students to assess" />
          ) : (
            <div className="grid gap-5 xl:grid-cols-2">
              <AssessmentForm students={list} />
              <MockInterviewForm students={list} />
            </div>
          )
        }
      </QueryState>
    </>
  );
}

function StudentSelect({
  students,
  value,
  onChange,
}: {
  students: Schemas["Student"][];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <SelectField label="Student" value={value} onChange={(e) => onChange(e.target.value)} required>
      <option value="">Choose a student</option>
      {students.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name} ({s.roll_number})
        </option>
      ))}
    </SelectField>
  );
}

function AssessmentForm({ students }: { students: Schemas["Student"][] }) {
  const queryClient = useQueryClient();
  const rubrics = useQuery({
    queryKey: ["rubrics"],
    queryFn: async () => unwrap(await api.GET("/api/v1/assessments/rubrics/")),
  });
  const [student, setStudent] = useState("");
  const [rubricId, setRubricId] = useState("");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [scores, setScores] = useState<Record<number, string>>({});
  const [skill, setSkill] = useState<{ id: number; name: string } | null>(null);
  const [notes, setNotes] = useState("");
  const rubric = rubrics.data?.find((r) => String(r.id) === rubricId);
  const save = useMutation({
    meta: { toast: "Assessment recorded" },
    mutationFn: () =>
      post("/api/v1/assessments/", {
        student_id: Number(student),
        rubric_id: Number(rubricId),
        title,
        assessed_on: date,
        notes,
        skill_id: skill?.id ?? null,
        scores: rubric?.criteria.map((c) => ({ criterion_id: c.id, score: Number(scores[c.id!] ?? 0) })) ?? [],
      }),
    onSuccess: () => {
      setScores({});
      setTitle("");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["assessments"] });
    },
  });
  return (
    <Card>
      <CardHeader title="Record an assessment" />
      <CardBody>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <StudentSelect students={students} value={student} onChange={setStudent} />
          <SelectField
            label="Rubric"
            value={rubricId}
            onChange={(e) => {
              setRubricId(e.target.value);
              setScores({});
            }}
            required
          >
            <option value="">Choose a rubric</option>
            {rubrics.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.kind})
              </option>
            ))}
          </SelectField>
          <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <TextField label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          {rubric?.kind === "technical" && (
            <div className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">Skill assessed</span>
              {skill ? (
                <span className="flex items-center gap-2">
                  {skill.name}
                  <Button variant="ghost" onClick={() => setSkill(null)}>
                    Change
                  </Button>
                </span>
              ) : (
                <SkillPicker label="Search skills…" onPick={(s) => setSkill({ id: s.id, name: s.name })} />
              )}
            </div>
          )}
          {rubric?.criteria.map((c) => (
            <TextField
              key={c.id}
              label={`${c.name} (out of ${c.max_score})`}
              type="number"
              min={0}
              max={c.max_score}
              step="0.5"
              value={scores[c.id!] ?? ""}
              onChange={(e) => setScores({ ...scores, [c.id!]: e.target.value })}
              required
            />
          ))}
          <TextAreaField label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          {save.error ? <FormError message={errorMessage(save.error)} /> : null}
          <Button type="submit" disabled={save.isPending || !student || !rubric || !title}>
            Save assessment
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function MockInterviewForm({ students }: { students: Schemas["Student"][] }) {
  const queryClient = useQueryClient();
  const [student, setStudent] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [focus, setFocus] = useState("");
  const [technical, setTechnical] = useState("");
  const [communication, setCommunication] = useState("");
  const [problemSolving, setProblemSolving] = useState("");
  const [feedback, setFeedback] = useState("");
  const [ratings, setRatings] = useState<{ skill_id: number; name: string; level: number }[]>([]);
  const save = useMutation({
    meta: { toast: "Mock interview recorded" },
    mutationFn: () =>
      post("/api/v1/assessments/mock-interviews/", {
        student_id: Number(student),
        conducted_on: date,
        role_focus: focus,
        feedback,
        technical_score: Number(technical),
        communication_score: Number(communication),
        problem_solving_score: Number(problemSolving),
        skill_ratings: ratings.map(({ skill_id, level }) => ({ skill_id, level })),
      }),
    onSuccess: () => {
      setFeedback("");
      setRatings([]);
      queryClient.invalidateQueries({ queryKey: ["mock-interviews"] });
    },
  });
  return (
    <Card>
      <CardHeader title="Record a mock interview" />
      <CardBody>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <StudentSelect students={students} value={student} onChange={setStudent} />
          <TextField label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          <TextField
            label="Role focus"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="e.g. Backend Engineer"
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <TextField
              label="Technical (0–100)"
              type="number"
              min={0}
              max={100}
              value={technical}
              onChange={(e) => setTechnical(e.target.value)}
              required
            />
            <TextField
              label="Communication (0–100)"
              type="number"
              min={0}
              max={100}
              value={communication}
              onChange={(e) => setCommunication(e.target.value)}
              required
            />
            <TextField
              label="Problem solving (0–100)"
              type="number"
              min={0}
              max={100}
              value={problemSolving}
              onChange={(e) => setProblemSolving(e.target.value)}
              required
            />
          </div>
          <fieldset className="flex flex-col gap-2 text-sm">
            <legend className="mb-1 font-medium">Skills observed</legend>
            {ratings.map((r, i) => (
              <div key={r.skill_id} className="flex items-center gap-2">
                <span className="flex-1">{r.name}</span>
                <select
                  aria-label={`Level for ${r.name}`}
                  value={r.level}
                  onChange={(e) =>
                    setRatings(ratings.map((x, j) => (j === i ? { ...x, level: Number(e.target.value) } : x)))
                  }
                  className="h-8 rounded-md border border-border bg-surface px-2"
                >
                  <option value={1}>Beginner</option>
                  <option value={2}>Intermediate</option>
                  <option value={3}>Advanced</option>
                  <option value={4}>Expert</option>
                </select>
                <Button
                  variant="ghost"
                  onClick={() => setRatings(ratings.filter((_, j) => j !== i))}
                  aria-label={`Remove ${r.name}`}
                >
                  ×
                </Button>
              </div>
            ))}
            <SkillPicker
              label="Add a skill…"
              exclude={ratings.map((r) => r.skill_id)}
              onPick={(s) => setRatings([...ratings, { skill_id: s.id, name: s.name, level: 2 }])}
            />
          </fieldset>
          <TextAreaField label="Feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          {save.error ? <FormError message={errorMessage(save.error)} /> : null}
          <Button
            type="submit"
            disabled={save.isPending || !student || !technical || !communication || !problemSolving}
          >
            Save mock interview
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
