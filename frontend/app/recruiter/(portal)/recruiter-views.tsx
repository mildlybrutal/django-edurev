"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BriefcaseBusiness, CircleCheck } from "lucide-react";
import { AppFrame, CenteredMessage } from "@/components/shell/app-frame";
import { ResumeViewerButton } from "@/components/domain/resume-panel";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { QueryState } from "@/components/ui/states";
import { RegistrationBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { get } from "@/lib/api/request";
import type { Candidate, CandidatePage } from "@/lib/api/types";
import { useLogout, useRecruiterMe } from "@/lib/auth/session";

type RecruiterDrive = {
  drive_id: number;
  company: string;
  role: string;
  drive_date: string | null;
  expires_at: string;
  allowed_fields: string[];
  candidate_scope: string;
  candidates: number;
};

const RECRUITER_NAV = [{ href: "/recruiter", label: "My Drives", icon: BriefcaseBusiness }];

/** Recruiter-portal chrome. Separate session from the internal portal; the API enforces access. */
export function RecruiterShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me, isPending, isError } = useRecruiterMe();
  const logout = useLogout("recruiter");
  useEffect(() => {
    if (!isPending && !isError && !me) router.replace(`/recruiter/login?next=${encodeURIComponent(pathname)}`);
  }, [isPending, isError, me, pathname, router]);
  if (!me) return <CenteredMessage>{isError ? "Could not reach the server." : "Loading…"}</CenteredMessage>;
  return (
    <AppFrame
      title="Recruiter portal"
      home="/recruiter"
      items={RECRUITER_NAV}
      email={me.email}
      onSignOut={() => logout.mutate(undefined, { onSettled: () => router.replace("/recruiter/login") })}
      signingOut={logout.isPending}
    >
      {children}
    </AppFrame>
  );
}

export function RecruiterHome() {
  const drives = useQuery({
    queryKey: ["recruiter", "drives"],
    queryFn: () => get<RecruiterDrive[]>("/api/v1/recruiter/drives/"),
  });
  return (
    <>
      <PageHeader
        title="Your drives"
        description="Drives the placement cell has given you access to, until the stated expiry."
      />
      <QueryState query={drives}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No active access">Your access may have expired. Contact the placement cell.</EmptyState>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {list.map((d) => (
                <Card key={d.drive_id}>
                  <CardHeader
                    title={
                      <Link href={`/recruiter/drives/${d.drive_id}`} className="hover:underline">
                        {d.company} — {d.role}
                      </Link>
                    }
                    description={`Access until ${new Date(d.expires_at).toLocaleString()}`}
                  />
                  <CardBody className="flex flex-col gap-2 text-sm">
                    <p>
                      <span className="font-semibold tabular-nums">{d.candidates}</span>{" "}
                      {d.candidate_scope === "shortlisted" ? "shortlisted" : "registered"} candidates
                    </p>
                    <p className="text-xs text-muted">Visible fields: {d.allowed_fields.join(", ")}</p>
                    <Link href={`/recruiter/drives/${d.drive_id}`} className="text-primary">
                      View candidates
                    </Link>
                  </CardBody>
                </Card>
              ))}
            </div>
          )
        }
      </QueryState>
    </>
  );
}

export function CandidateSearch({ driveId }: { driveId: number }) {
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [minCompat, setMinCompat] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const params = new URLSearchParams({
    page: String(page),
    ...(q && { q }),
    ...(department && { department }),
    ...(minCompat && { min_compatibility: minCompat }),
  });
  const results = useQuery({
    queryKey: ["recruiter", "candidates", driveId, params.toString()],
    queryFn: () => get<CandidatePage>(`/api/v1/recruiter/drives/${driveId}/candidates/?${params}`),
  });
  const fields = new Set(results.data?.fields ?? []);
  return (
    <>
      <PageHeader
        title="Candidates"
        description="Only students registered for this drive, and only the fields the placement cell released, are shown. Your activity is logged."
        actions={
          <Link href="/recruiter" className="text-sm text-primary">
            All drives
          </Link>
        }
      />
      <div className="grid gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Filter" />
          <CardBody className="flex flex-col gap-4 text-sm">
            {fields.has("skills") && (
              <TextField
                label="Skill"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
                placeholder="e.g. Django, frontend framework"
              />
            )}
            {fields.has("compatibility") && (
              <TextField
                label="Min skill match %"
                type="number"
                min={0}
                max={100}
                value={minCompat}
                onChange={(e) => {
                  setMinCompat(e.target.value);
                  setPage(1);
                }}
              />
            )}
            {results.data?.facets.department && (
              <Facet
                title="Department"
                items={results.data.facets.department}
                active={department}
                onPick={(v) => {
                  setDepartment(v === department ? "" : v);
                  setPage(1);
                }}
              />
            )}
            {results.data?.facets.skills && (
              <Facet
                title="Top skills"
                items={results.data.facets.skills}
                active={q}
                onPick={(v) => {
                  setQ(v === q ? "" : v);
                  setPage(1);
                }}
              />
            )}
            {results.data?.facets.compatibility && (
              <Facet title="Skill match" items={results.data.facets.compatibility} />
            )}
          </CardBody>
        </Card>
        <div className="flex flex-col gap-5">
          <Card>
            <QueryState query={results}>
              {(r) =>
                r.results.length === 0 ? (
                  <CardBody>
                    <EmptyState title="No candidates match" />
                  </CardBody>
                ) : (
                  <>
                    <Table caption="Candidates">
                      <thead>
                        <tr>
                          <Th>Candidate</Th>
                          {fields.has("compatibility") && <Th>Skill match</Th>}
                          {fields.has("skills") && <Th>Key skills</Th>}
                          {fields.has("registration_status") && <Th>Status</Th>}
                        </tr>
                      </thead>
                      <tbody>
                        {r.results.map((c) => (
                          <tr key={c.id} className={selected === c.id ? "bg-primary-soft/40" : undefined}>
                            <Td>
                              <button
                                type="button"
                                className="text-left font-medium hover:underline"
                                onClick={() => setSelected(c.id)}
                              >
                                {c.name ?? `Candidate #${c.id}`}
                              </button>
                              {(c.department || c.graduation_year) && (
                                <span className="block text-xs text-muted">
                                  {[c.department?.code, c.graduation_year].filter(Boolean).join(" · ")}
                                </span>
                              )}
                            </Td>
                            {fields.has("compatibility") && (
                              <Td className="tabular-nums">
                                {c.compatibility == null ? "—" : `${c.compatibility.toFixed(0)}%`}
                              </Td>
                            )}
                            {fields.has("skills") && (
                              <Td className="text-sm">{c.skills?.map((s) => s.skill).join(", ") || "—"}</Td>
                            )}
                            {fields.has("registration_status") && (
                              <Td>
                                <RegistrationBadge status={c.registration_status} />
                              </Td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                    <div className="flex items-center justify-between px-5 py-2.5 text-sm">
                      <span className="text-muted">{r.count} candidates</span>
                      <span className="flex gap-2">
                        <Button variant="ghost" disabled={!r.previous} onClick={() => setPage((x) => x - 1)}>
                          Previous
                        </Button>
                        <Button variant="ghost" disabled={!r.next} onClick={() => setPage((x) => x + 1)}>
                          Next
                        </Button>
                      </span>
                    </div>
                  </>
                )
              }
            </QueryState>
          </Card>
          {selected && <CandidateProfile driveId={driveId} id={selected} />}
        </div>
      </div>
    </>
  );
}

function Facet({
  title,
  items,
  active,
  onPick,
}: {
  title: string;
  items: { value: string; count: number }[];
  active?: string;
  onPick?: (v: string) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 font-medium">{title}</p>
      <ul className="flex flex-col gap-1">
        {items.map((i) => (
          <li key={i.value}>
            {onPick ? (
              <button
                type="button"
                onClick={() => onPick(i.value)}
                aria-pressed={active === i.value}
                className={`flex w-full justify-between rounded px-1.5 py-0.5 text-left hover:bg-surface-muted ${active === i.value ? "bg-primary-soft text-primary" : ""}`}
              >
                <span>{i.value}</span>
                <span className="tabular-nums text-muted">{i.count}</span>
              </button>
            ) : (
              <span className="flex justify-between px-1.5">
                <span>{i.value}</span>
                <span className="tabular-nums text-muted">{i.count}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CandidateProfile({ driveId, id }: { driveId: number; id: number }) {
  const candidate = useQuery({
    queryKey: ["recruiter", "candidate", driveId, id],
    queryFn: () => get<Candidate>(`/api/v1/recruiter/drives/${driveId}/candidates/${id}/`),
  });
  return (
    <Card>
      <QueryState query={candidate}>
        {(c) => (
          <>
            <CardHeader
              title={c.name ?? `Candidate #${c.id}`}
              description="Released fields only."
              action={
                c.resume_available ? (
                  <ResumeViewerButton path={`/api/v1/recruiter/drives/${driveId}/candidates/${c.id}/resume/`} />
                ) : undefined
              }
            />
            <CardBody className="flex flex-col gap-4 text-sm">
              <dl className="grid grid-cols-[10rem_1fr] gap-y-1.5">
                {c.email && (
                  <>
                    <dt className="text-muted">Email</dt>
                    <dd>{c.email}</dd>
                  </>
                )}
                {c.department && (
                  <>
                    <dt className="text-muted">Department</dt>
                    <dd>{c.department.name}</dd>
                  </>
                )}
                {c.graduation_year && (
                  <>
                    <dt className="text-muted">Graduation year</dt>
                    <dd>{c.graduation_year}</dd>
                  </>
                )}
                {c.cgpa && (
                  <>
                    <dt className="text-muted">CGPA</dt>
                    <dd>{c.cgpa}</dd>
                  </>
                )}
                {c.compatibility != null && (
                  <>
                    <dt className="text-muted">Skill match</dt>
                    <dd>{c.compatibility.toFixed(0)}%</dd>
                  </>
                )}
                {c.readiness && (
                  <>
                    <dt className="text-muted">Readiness</dt>
                    <dd>
                      {c.readiness.overall.toFixed(0)}% (technical {c.readiness.technical.toFixed(0)}, aptitude{" "}
                      {c.readiness.aptitude.toFixed(0)}, communication {c.readiness.communication.toFixed(0)}, projects{" "}
                      {c.readiness.project_depth.toFixed(0)}
                      {c.readiness.coding_activity !== undefined &&
                        `, coding ${c.readiness.coding_activity.toFixed(0)}`}
                      )
                    </dd>
                  </>
                )}
                {c.coding_activity && (
                  <>
                    <dt className="text-muted">Coding activity</dt>
                    <dd>
                      {c.coding_activity.score === null ? "Not synced" : `${c.coding_activity.score.toFixed(0)}%`}
                      {c.coding_activity.platforms.length > 0 && (
                        <span className="text-muted">
                          {" "}
                          (
                          {c.coding_activity.platforms
                            .map((p) => `${p.platform} ${p.rating === null ? "—" : p.rating.toFixed(0)}`)
                            .join(", ")}
                          ; unverified public activity)
                        </span>
                      )}
                    </dd>
                  </>
                )}
                {c.registration_status && (
                  <>
                    <dt className="text-muted">Status</dt>
                    <dd>
                      <RegistrationBadge status={c.registration_status} />
                    </dd>
                  </>
                )}
              </dl>
              {c.skills && (
                <div>
                  <p className="mb-1.5 font-medium">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {c.skills.map((s) => (
                      <Badge key={s.skill} tone={s.verified ? "success" : "neutral"}>
                        {s.verified && <CircleCheck aria-hidden="true" className="size-3.5" />}
                        {s.skill} · {s.level}
                        <span className="sr-only">{s.verified ? "(verified)" : "(unverified)"}</span>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {c.evidence && (
                <div>
                  <p className="mb-1.5 font-medium">Evidence</p>
                  <ul className="flex flex-col gap-1">
                    {c.evidence.map((e, i) => (
                      <li key={i}>
                        {e.title}{" "}
                        <span className="text-muted">
                          · {e.type} · {e.verification}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
          </>
        )}
      </QueryState>
    </Card>
  );
}
