"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Circle, CircleCheck, Clock } from "lucide-react";
import { CodingActivityCard } from "@/components/domain/coding-activity";
import { ResumeCard } from "@/components/domain/resume-panel";
import { SkillProfileList } from "@/components/domain/skill-profile";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import { FormError } from "@/components/ui/form";
import { Meter } from "@/components/ui/meter";
import { errorMessage, QueryState } from "@/components/ui/states";
import { get, patch } from "@/lib/api/request";
import type { SkillProfile } from "@/lib/api/types";

export function ProfileView() {
  const query = useQuery({
    queryKey: ["profile", "me"],
    queryFn: () => get<SkillProfile>("/api/v1/students/me/profile/"),
  });
  return (
    <QueryState query={query}>
      {(p) => (
        <>
          <PageHeader
            title="My Profile"
            description="Your academic record and the skill profile built from your evidence."
          />
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <div className="flex flex-col gap-5">
              <Card>
                <CardHeader
                  title="Academic record"
                  description={
                    p.student.academic_record_verified !== false
                      ? "Maintained by the placement cell. Contact them if something is wrong."
                      : "You entered these at sign-up. The placement cell confirms them before drives rely on them."
                  }
                  action={
                    p.student.academic_record_verified !== false ? (
                      <Badge tone="success">
                        <CircleCheck aria-hidden="true" className="size-3.5" />
                        Confirmed
                      </Badge>
                    ) : (
                      <Badge tone="warning">
                        <Clock aria-hidden="true" className="size-3.5" />
                        Awaiting confirmation
                      </Badge>
                    )
                  }
                />
                <CardBody>
                  <dl className="grid grid-cols-[9rem_1fr] gap-y-2 text-sm">
                    <dt className="text-muted">Name</dt>
                    <dd>{p.student.name}</dd>
                    <dt className="text-muted">Registration no.</dt>
                    <dd>{p.student.roll_number}</dd>
                    <dt className="text-muted">Department</dt>
                    <dd>{p.student.department.name}</dd>
                    <dt className="text-muted">Graduation year</dt>
                    <dd>{p.student.graduation_year}</dd>
                    <dt className="text-muted">CGPA</dt>
                    <dd className="tabular-nums">{p.student.cgpa}</dd>
                    <dt className="text-muted">Active backlogs</dt>
                    <dd className="tabular-nums">{p.student.active_backlogs}</dd>
                    <dt className="text-muted">Mentor</dt>
                    <dd>{p.student.mentor?.name ?? "Not assigned"}</dd>
                  </dl>
                </CardBody>
              </Card>
              <EditLinks student={p.student} />
              <ResumeCard editable />
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
                        <span className={c.done ? "text-muted line-through" : ""}>{c.label}</span>
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            </div>
            <div className="flex flex-col gap-5">
              <CodingActivityCard editable />
              <Card>
                <CardHeader
                  title="Skill profile"
                  description="Each level is backed by evidence. Select a skill to see why it is there."
                />
                <CardBody>
                  <SkillProfileList claims={p.claims} />
                </CardBody>
              </Card>
            </div>
          </div>
        </>
      )}
    </QueryState>
  );
}

function EditLinks({ student }: { student: SkillProfile["student"] }) {
  const queryClient = useQueryClient();
  const [headline, setHeadline] = useState(student.headline ?? "");
  const [linkedin, setLinkedin] = useState(student.linkedin_url ?? "");
  const save = useMutation({
    meta: { toast: "Profile details saved" },
    mutationFn: () => patch("/api/v1/students/me/", { headline, linkedin_url: linkedin }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile"] }),
  });
  return (
    <Card>
      <CardHeader title="About you" />
      <CardBody>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <TextField
            label="Headline"
            value={headline}
            maxLength={160}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. Backend developer interested in fintech"
          />
          <p className="-mt-1 text-xs text-muted">GitHub and LeetCode are linked under Coding activity.</p>
          <TextField
            label="LinkedIn profile URL"
            placeholder="https://www.linkedin.com/in/your-name"
            type="url"
            value={linkedin}
            onChange={(e) => setLinkedin(e.target.value)}
          />
          {save.error ? <FormError message={errorMessage(save.error)} /> : null}
          <Button type="submit" disabled={save.isPending} className="self-start">
            Save
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
