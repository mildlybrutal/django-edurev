"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Circle, CircleCheck, Clock } from "lucide-react";
import { AssessmentHistory } from "@/app/student/assessments/assessments-view";
import { ReadinessHistory } from "@/app/student/progress/progress-view";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Meter } from "@/components/ui/meter";
import { QueryState } from "@/components/ui/states";
import { VerificationBadge } from "@/components/ui/status";
import { Tabs } from "@/components/ui/tabs";
import { api, unwrap } from "@/lib/api/client";
import { get, patch } from "@/lib/api/request";
import { useMe } from "@/lib/auth/session";
import type { SkillProfile } from "@/lib/api/types";
import { useState } from "react";
import { CodingActivityCard } from "./coding-activity";
import { ResumeCard } from "./resume-panel";
import { SkillProfileList } from "./skill-profile";

type Tab = "profile" | "readiness" | "evidence" | "assessments";

/** Staff view of one student (faculty for mentees, placement cell for anyone in the institution). */
export function StudentDetail({ id }: { id: number }) {
  const [tab, setTab] = useState<Tab>("profile");
  const profile = useQuery({
    queryKey: ["profile", id],
    queryFn: () => get<SkillProfile>(`/api/v1/students/${id}/profile/`),
  });
  return (
    <QueryState query={profile}>
      {(p) => (
        <>
          <PageHeader
            title={p.student.name}
            description={`${p.student.roll_number} · ${p.student.department.code} · Class of ${p.student.graduation_year} · CGPA ${p.student.cgpa} · ${p.student.active_backlogs} active backlog(s)`}
            actions={<AcademicConfirm studentId={id} verified={p.student.academic_record_verified !== false} />}
          />
          <Tabs
            label="Student sections"
            value={tab}
            onChange={setTab}
            tabs={[
              { value: "profile", label: "Skill profile" },
              { value: "readiness", label: "Readiness" },
              { value: "evidence", label: "Evidence" },
              { value: "assessments", label: "Assessments" },
            ]}
          />
          {tab === "profile" && (
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
              <Card className="self-start">
                <CardHeader title="Skill profile" />
                <CardBody>
                  <SkillProfileList claims={p.claims} />
                </CardBody>
              </Card>
              <div className="flex flex-col gap-5">
                <Card>
                  <CardHeader
                    title="Profile completion"
                    action={<span className="font-semibold tabular-nums">{p.completion.percent}%</span>}
                  />
                  <CardBody className="flex flex-col gap-3">
                    <Meter value={p.completion.percent} label="Profile completion" />
                    <ul className="flex flex-col gap-1.5 text-sm">
                      {p.completion.checks.map((c) => (
                        <li key={c.key} className="flex items-center gap-2">
                          {c.done ? (
                            <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-success" />
                          ) : (
                            <Circle aria-hidden="true" className="size-4 shrink-0 text-muted" />
                          )}
                          {c.label}
                        </li>
                      ))}
                    </ul>
                    <p className="text-sm text-muted">Mentor: {p.student.mentor?.name ?? "not assigned"}</p>
                  </CardBody>
                </Card>
                <CodingActivityCard student={id} />
                <ResumeCard student={id} />
              </div>
            </div>
          )}
          {tab === "readiness" && <ReadinessHistory studentId={id} />}
          {tab === "evidence" && <EvidenceList studentId={id} />}
          {tab === "assessments" && <AssessmentHistory studentId={id} showHeader={false} />}
        </>
      )}
    </QueryState>
  );
}

function EvidenceList({ studentId }: { studentId: number }) {
  const evidence = useQuery({
    queryKey: ["evidence", "student", studentId],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/evidence/", { params: { query: { student: studentId } } })).results,
  });
  return (
    <Card>
      <QueryState query={evidence}>
        {(rows) =>
          rows.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No evidence" />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((e) => (
                <li key={e.id} className="px-5 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{e.title}</span>
                    <Badge>{e.source_label}</Badge>
                    <VerificationBadge status={e.verification_status} />
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {e.skill_tags.map((t) => `${t.skill} (${t.level_label})`).join(", ") || "No skills tagged"}
                  </p>
                  {e.source_url && (
                    <a
                      className="text-xs text-primary hover:underline"
                      href={e.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {e.source_url}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )
        }
      </QueryState>
    </Card>
  );
}

/** Self-declared academics (student sign-up) until the placement cell confirms them. */
function AcademicConfirm({ studentId, verified }: { studentId: number; verified: boolean }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const confirm = useMutation({
    meta: { toast: "Academic record confirmed" },
    mutationFn: () => patch(`/api/v1/students/${studentId}/`, { academic_record_verified: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile", studentId] }),
  });
  if (verified) return null;
  const canConfirm = me?.roles.some((r) => r === "placement_officer" || r === "placement_head" || r === "admin");
  return (
    <div className="flex items-center gap-2">
      <Badge tone="warning">
        <Clock aria-hidden="true" className="size-3.5" />
        Academics self-declared
      </Badge>
      {canConfirm && (
        <Button size="sm" variant="secondary" onClick={() => confirm.mutate()} disabled={confirm.isPending}>
          Confirm academic record
        </Button>
      )}
    </div>
  );
}
