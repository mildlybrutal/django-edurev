"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { BarList, Columns } from "@/components/charts/bar-list";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { pct, StatCard, StatGrid } from "@/components/ui/stat";
import { QueryState } from "@/components/ui/states";
import { DriveStatusBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { get } from "@/lib/api/request";
import type { DemandAcrossDrives, Overview } from "@/lib/api/types";

export function PlacementDashboard() {
  const overview = useQuery({
    queryKey: ["reports", "overview"],
    queryFn: () => get<Overview>("/api/v1/reports/overview/"),
  });
  const demand = useQuery({
    queryKey: ["reports", "demand"],
    queryFn: () => get<DemandAcrossDrives>("/api/v1/reports/demand/"),
  });
  return (
    <QueryState query={overview}>
      {(o) => (
        <>
          <PageHeader
            title="Placement dashboard"
            description="How ready the batch is for upcoming drives. All figures are computed from stored evidence and drive results."
          />
          <StatGrid>
            <StatCard
              label="Total students"
              value={o.total_students}
              hint={`${o.students_with_readiness} with a readiness score`}
            />
            <StatCard label="Active drives" value={o.active_drives} />
            <StatCard
              label="Eligible students"
              value={o.eligible_students}
              hint="Eligible for at least one active drive"
            />
            <StatCard
              label="Average readiness"
              value={pct(o.average_readiness)}
              hint={
                <Link className="text-primary" href="/placement/analytics">
                  Batch analytics
                </Link>
              }
            />
          </StatGrid>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-2">
            <Card className="self-start">
              <CardHeader title="Batch readiness distribution" description="Latest general readiness per student." />
              <CardBody>
                {o.students_with_readiness === 0 ? (
                  <EmptyState title="No readiness computed yet">Run batch readiness from Batch Analytics.</EmptyState>
                ) : (
                  <Columns
                    title="Students per readiness band"
                    rows={[...o.readiness_distribution]
                      .reverse()
                      .map((b) => ({ label: b.band, count: b.count, percent: b.percent }))}
                  />
                )}
              </CardBody>
            </Card>
            <Card>
              <CardHeader
                title="Skill supply vs demand"
                description="Skills required by active drives, and the share of students who meet the level."
                action={
                  <Link href="/placement/reports" className="text-sm text-primary">
                    Full report
                  </Link>
                }
              />
              <CardBody>
                <QueryState query={demand}>
                  {(d) =>
                    d.skills.length === 0 ? (
                      <EmptyState title="No active drives with requirements" />
                    ) : (
                      <BarList
                        title="Student supply per demanded skill"
                        rows={d.skills.slice(0, 8).map((s) => ({
                          key: s.skill_id,
                          label: `${s.skill} (${s.required_level}+)`,
                          value: s.supply_percent,
                          note: `${s.active_drives} active drive(s)`,
                          cluster: s.cluster ?? null,
                        }))}
                      />
                    )
                  }
                </QueryState>
              </CardBody>
            </Card>
            <Card className="xl:col-span-2">
              <CardHeader
                title="Recent drives"
                action={
                  <Link href="/placement/drives" className="text-sm text-primary">
                    All drives
                  </Link>
                }
              />
              {o.recent_drives.length === 0 ? (
                <CardBody>
                  <EmptyState title="No drives yet" />
                </CardBody>
              ) : (
                <Table caption="Recent drives">
                  <thead>
                    <tr>
                      <Th>Company and role</Th>
                      <Th>Status</Th>
                      <Th>Eligible</Th>
                      <Th>Registered</Th>
                      <Th>Avg skill match</Th>
                      <Th>Avg readiness</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.recent_drives.map((d) => (
                      <tr key={d.id}>
                        <Td>
                          <Link href={`/placement/drives/${d.id}`} className="font-medium hover:underline">
                            {d.company}
                          </Link>
                          <span className="block text-xs text-muted">{d.role}</span>
                        </Td>
                        <Td>
                          <DriveStatusBadge status={d.status} label={d.status_label} />
                        </Td>
                        <Td className="tabular-nums">{d.matched ? d.eligible : "—"}</Td>
                        <Td className="tabular-nums">{d.registered}</Td>
                        <Td className="tabular-nums">{pct(d.average_compatibility)}</Td>
                        <Td className="tabular-nums">{pct(d.average_readiness)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
            <Card className="xl:col-span-2">
              <CardHeader
                title="Top skill gaps"
                description="Students with a gap in each skill across active drives."
              />
              <CardBody>
                {o.top_gaps.length === 0 ? (
                  <EmptyState title="No gap analyses yet">Run matching on a drive.</EmptyState>
                ) : (
                  <BarList
                    title="Students with each gap"
                    max={Math.max(...o.top_gaps.map((g) => g.students))}
                    rows={o.top_gaps.map((g) => ({
                      key: g.skill_id,
                      label: g.skill,
                      value: g.students,
                      display: `${g.students} students`,
                      note: `${g.missing} with no evidence · ${g.unverified} unverified only · ${g.high_impact} high impact`,
                      cluster: g.cluster ?? null,
                    }))}
                  />
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </QueryState>
  );
}
