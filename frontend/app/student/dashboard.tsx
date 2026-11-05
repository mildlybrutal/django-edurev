"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, BriefcaseBusiness, CircleGauge, Flag, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { RadarChart, readinessAxes } from "@/components/charts/radar";
import { LevelPips } from "@/components/domain/skill-profile";
import { TimeBudget } from "@/components/domain/time-budget";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ModuleRow, NextTag } from "@/components/ui/module-spine";
import { pct, StatCard, StatGrid } from "@/components/ui/stat";
import { QueryState } from "@/components/ui/states";
import { EligibilityBadge, ImpactBadge, RegistrationBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { get } from "@/lib/api/request";
import type { StudentDashboard } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { HUE, hueFor } from "@/lib/modules";

const icon = "size-[18px]";

export function StudentDashboardView() {
  const query = useQuery({
    queryKey: ["dashboard", "student"],
    queryFn: () => get<StudentDashboard>("/api/v1/dashboard/student/"),
  });
  return (
    <QueryState query={query}>
      {(d) => {
        const gaps = d.drives
          .flatMap((dr) => dr.top_gaps.map((g) => ({ ...g, drive: dr })))
          .sort((a, b) => b.impact_score - a.impact_score)
          .slice(0, 4);
        return (
          <>
            <PageHeader
              title={`Hello, ${d.student.name.split(" ")[0]}`}
              description={`${d.student.department} · ${d.student.roll_number} · ${d.drives.length} drive${d.drives.length === 1 ? "" : "s"} open. Where you stand, and what to do next.`}
            />
            <StatGrid>
              <StatCard
                hue="cobalt"
                icon={<UserRoundCheck aria-hidden="true" className={icon} strokeWidth={1.75} />}
                label="Profile completion"
                value={`${d.cards.profile_completion}%`}
                hint={
                  d.cards.profile_completion < 100 ? (
                    <Link className="text-primary hover:underline" href="/student/profile">
                      Complete your profile
                    </Link>
                  ) : (
                    "Every profile check is done"
                  )
                }
              />
              <StatCard
                hue="teal"
                icon={<BadgeCheck aria-hidden="true" className={icon} strokeWidth={1.75} />}
                label="Verified evidence"
                value={
                  <>
                    {d.cards.verified_evidence}
                    <span className="text-base font-normal text-muted"> / {d.cards.total_evidence}</span>
                  </>
                }
                hint="Verified by your mentor or recorded by the institution"
              />
              <StatCard
                hue="green"
                icon={<BriefcaseBusiness aria-hidden="true" className={icon} strokeWidth={1.75} />}
                label="Eligible drives"
                value={d.cards.eligible_drives}
                hint="Active drives whose criteria you meet"
              />
              <StatCard
                hue="marigold"
                icon={<CircleGauge aria-hidden="true" className={icon} strokeWidth={1.75} />}
                label="Readiness"
                value={pct(d.cards.readiness)}
                hint="General readiness across all dimensions"
              />
            </StatGrid>

            <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
              <div className="flex min-w-0 flex-col gap-5">
                <Card>
                  <CardHeader
                    title="Your next steps"
                    description={
                      d.plan
                        ? "Open tasks from your preparation plan, in order. Start with the one marked NEXT."
                        : "No active plan yet. Your highest-impact gap is where to start."
                    }
                    action={
                      <Link href="/student/plan" className="text-sm text-primary hover:underline">
                        Full plan
                      </Link>
                    }
                  />
                  <CardBody className="flex flex-col gap-3">
                    {d.plan && (
                      <TimeBudget
                        start={d.plan.start_date}
                        end={d.plan.end_date}
                        driveDate={d.plan.drive_date}
                        company={d.plan.company}
                        done={d.plan.done}
                        total={d.plan.total}
                      />
                    )}
                    {d.tasks.length > 0 ? (
                      <ol className="flex flex-col gap-2">
                        {d.tasks.map((t, i) => (
                          <li key={t.id}>
                            <ModuleRow index={i + 1} cluster={t.cluster} next={i === 0}>
                              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
                                <span className="flex min-w-0 flex-wrap items-center gap-2">
                                  <span className="font-medium">{t.title}</span>
                                  {i === 0 && <NextTag />}
                                  {t.is_checkpoint && (
                                    <Badge tone="info">
                                      <Flag aria-hidden="true" className="size-3.5" />
                                      Checkpoint
                                    </Badge>
                                  )}
                                </span>
                                <span
                                  className={cn(
                                    "text-xs tabular-nums",
                                    t.overdue ? "font-medium text-danger" : "text-muted",
                                  )}
                                >
                                  {t.overdue ? "Overdue · " : "Due "}
                                  {t.due_date}
                                </span>
                              </div>
                            </ModuleRow>
                          </li>
                        ))}
                      </ol>
                    ) : gaps.length > 0 ? (
                      <ModuleRow index={1} cluster={gaps[0].cluster} next>
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className="font-medium">{gaps[0].skill}</span>
                          <NextTag>Start here</NextTag>
                          <span className="text-muted">for {gaps[0].drive.company}</span>
                        </div>
                        <p className="mt-1 text-sm">{gaps[0].suggested_action}</p>
                        <Link
                          href={`/student/drives/${gaps[0].drive.id}`}
                          className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-next hover:underline"
                        >
                          Make a plan from this drive
                          <ArrowRight aria-hidden="true" className="size-4" />
                        </Link>
                      </ModuleRow>
                    ) : (
                      <EmptyState title="Nothing to do right now">
                        Open a placement drive to see your gaps and generate a dated plan.
                      </EmptyState>
                    )}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader
                    title="Top skill gaps"
                    description="Highest-impact gaps across your upcoming drives, coloured by module."
                  />
                  <CardBody>
                    {gaps.length === 0 ? (
                      <EmptyState title="No gaps found" />
                    ) : (
                      <ol className="flex flex-col gap-2">
                        {gaps.map((g, i) => (
                          <li key={`${g.drive.id}-${g.skill_id}`}>
                            <ModuleRow index={i + 1} cluster={g.cluster}>
                              <div className="flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium">{g.skill}</span>
                                <ImpactBadge level={g.impact} />
                                <Link
                                  href={`/student/drives/${g.drive.id}`}
                                  className="text-xs text-muted hover:text-primary hover:underline"
                                >
                                  for {g.drive.company}
                                </Link>
                              </div>
                              <p className="mt-0.5 text-sm text-muted tabular-nums">
                                {g.current} → {g.required}
                              </p>
                            </ModuleRow>
                          </li>
                        ))}
                      </ol>
                    )}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader
                    title="Your skill profile"
                    description="Solid pips are verified; outlined pips are claimed but not yet verified."
                    action={
                      <Link href="/student/profile" className="text-sm text-primary hover:underline">
                        Details
                      </Link>
                    }
                  />
                  <CardBody>
                    {d.skills.length ? (
                      <ul className="grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-3 sm:grid-cols-[repeat(2,minmax(0,1fr))]">
                        {d.skills.map((s) => (
                          <li key={s.skill} className="flex items-center justify-between gap-3 text-sm">
                            <span className="flex min-w-0 items-center gap-2">
                              <span
                                aria-hidden="true"
                                className={cn("size-2.5 shrink-0 rounded-sm", HUE[hueFor(s.cluster)].solid)}
                              />
                              <span className="truncate font-medium">{s.skill}</span>
                            </span>
                            <span className="flex shrink-0 items-center gap-2">
                              <LevelPips level={s.level} verified={s.verified_level} cluster={s.cluster} />
                              <span className="w-20 text-xs text-muted">
                                {s.level_label}
                                <span className="sr-only">{s.is_verified ? ", verified" : ", unverified"}</span>
                              </span>
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <EmptyState title="No skills yet">
                        <Link href="/student/evidence" className="text-primary">
                          Add evidence
                        </Link>{" "}
                        tagged with skills.
                      </EmptyState>
                    )}
                  </CardBody>
                </Card>
              </div>

              <div className="flex min-w-0 flex-col gap-5">
                <Card>
                  <CardHeader
                    title="Readiness"
                    description="Five dimensions, each explained on the Progress page."
                    action={
                      <Link href="/student/progress" className="text-sm text-primary hover:underline">
                        History
                      </Link>
                    }
                  />
                  <CardBody>
                    {d.readiness ? (
                      <RadarChart title="General readiness by dimension" axes={readinessAxes(d.readiness)} size={220} />
                    ) : (
                      <EmptyState title="Not computed yet">Add evidence to get your first readiness score.</EmptyState>
                    )}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader
                    title="Upcoming placement drives"
                    description="Eligibility and skill match are separate: one is criteria, the other evidence."
                    action={
                      <Link href="/student/drives" className="text-sm text-primary hover:underline">
                        All drives
                      </Link>
                    }
                  />
                  {d.drives.length === 0 ? (
                    <CardBody>
                      <EmptyState title="No open drives right now" />
                    </CardBody>
                  ) : (
                    <Table caption="Upcoming drives">
                      <thead>
                        <tr>
                          <Th>Drive</Th>
                          <Th>Eligibility</Th>
                          <Th className="text-right">Match</Th>
                          <Th>Registration</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.drives.map((drive) => (
                          <tr key={drive.id} className="transition-colors hover:bg-surface-muted">
                            <Td>
                              <Link href={`/student/drives/${drive.id}`} className="font-medium hover:underline">
                                {drive.company}
                              </Link>
                              <span className="block text-xs text-muted">
                                {drive.role}
                                {drive.drive_date && <span className="whitespace-nowrap"> · {drive.drive_date}</span>}
                              </span>
                            </Td>
                            <Td>
                              <EligibilityBadge eligible={drive.is_eligible} />
                            </Td>
                            <Td className="text-right font-medium tabular-nums">{drive.compatibility.toFixed(0)}%</Td>
                            <Td className="whitespace-nowrap">
                              <RegistrationBadge status={drive.registration?.status} />
                            </Td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>

                <Card>
                  <CardHeader title="Recent activity" />
                  <CardBody>
                    {d.activity.length === 0 ? (
                      <p className="text-sm text-muted">Nothing yet.</p>
                    ) : (
                      <ul className="flex flex-col gap-2.5 text-sm">
                        {d.activity.map((a, i) => (
                          <li key={i}>
                            {a.link ? (
                              <Link href={a.link} className="hover:underline">
                                {a.title}
                              </Link>
                            ) : (
                              a.title
                            )}
                            <span className="block text-xs text-muted">{new Date(a.at).toLocaleString()}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardBody>
                </Card>
              </div>
            </div>
          </>
        );
      }}
    </QueryState>
  );
}
