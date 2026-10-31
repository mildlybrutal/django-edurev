"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { BarList, Columns } from "@/components/charts/bar-list";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { FormError } from "@/components/ui/form";
import { Meter } from "@/components/ui/meter";
import { pct, StatCard, StatGrid } from "@/components/ui/stat";
import { errorMessage, QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { useMe } from "@/lib/auth/session";
import { get, post } from "@/lib/api/request";
import type {
  DepartmentRow,
  GapFrequencyRow,
  Overview,
  TrainingEffectiveness,
  VerificationCoverage,
} from "@/lib/api/types";

type Job = {
  id: number;
  status: string;
  total: number;
  processed: number;
  result: Record<string, unknown>;
  error: string;
  created_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
};

export function AnalyticsView() {
  const { data: me } = useMe();
  const institutional = !!me?.roles.some((r) => r === "placement_head" || r === "admin");
  const overview = useQuery({
    queryKey: ["reports", "overview"],
    queryFn: () => get<Overview>("/api/v1/reports/overview/"),
  });
  return (
    <>
      <PageHeader
        title="Batch Analytics"
        description="Cohort-level readiness, gaps and verification. Recompute readiness for the whole batch as a background job."
      />
      <BatchJob />
      <div className="grid gap-5 xl:grid-cols-2">
        <QueryState query={overview}>
          {(o) => (
            <Card>
              <CardHeader
                title="Readiness distribution"
                description={`${o.students_with_readiness} of ${o.total_students} students have a readiness score · average ${pct(o.average_readiness)}`}
              />
              <CardBody>
                {o.students_with_readiness === 0 ? (
                  <EmptyState title="Run batch readiness to see the distribution" />
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
          )}
        </QueryState>
        <GapFrequency />
        <Coverage />
        {institutional ? <Departments /> : null}
        {institutional ? <Training /> : null}
      </div>
    </>
  );
}

function BatchJob() {
  const queryClient = useQueryClient();
  const jobs = useQuery({
    queryKey: ["reports", "batch-jobs"],
    queryFn: () => get<Job[]>("/api/v1/reports/batch-readiness/"),
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === "queued" || j.status === "running") ? 1500 : false),
  });
  const start = useMutation({
    meta: { toast: "Batch readiness started", toastBody: "It runs in the background; progress shows below." },
    mutationFn: () => post<Job>("/api/v1/reports/batch-readiness/"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports", "batch-jobs"] }),
  });
  const latest = jobs.data?.[0];
  const running = latest && (latest.status === "queued" || latest.status === "running");
  const refreshedFor = useRef<number | null>(null);
  useEffect(() => {
    // When a run finishes, refresh the report queries once.
    if (latest && latest.status === "succeeded" && refreshedFor.current !== latest.id) {
      refreshedFor.current = latest.id;
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    }
  }, [latest, queryClient]);
  return (
    <Card className="mb-5">
      <CardHeader
        title="Batch readiness"
        description="Rebuilds skill profiles and readiness for every student on the Celery worker, then nudges low-readiness students and their mentors."
        action={
          <Button onClick={() => start.mutate()} disabled={start.isPending || !!running}>
            {running ? "Running…" : "Recompute for all students"}
          </Button>
        }
      />
      <CardBody className="flex flex-col gap-2 text-sm">
        {start.error ? <FormError message={errorMessage(start.error)} /> : null}
        {!latest ? (
          <p className="text-muted">Not run yet.</p>
        ) : (
          <>
            <p>
              Last run: <span className="capitalize">{latest.status}</span> · {latest.processed}/{latest.total} students
              {latest.duration_seconds != null && ` · ${latest.duration_seconds.toFixed(1)}s on the worker`}
              {latest.finished_at && ` · ${new Date(latest.finished_at).toLocaleString()}`}
            </p>
            {running && (
              <Meter
                value={latest.total ? (100 * latest.processed) / latest.total : 0}
                label="Batch readiness progress"
              />
            )}
            {latest.error && <FormError message={latest.error} />}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function GapFrequency() {
  const gaps = useQuery({
    queryKey: ["reports", "gaps"],
    queryFn: () => get<GapFrequencyRow[]>("/api/v1/reports/gaps/"),
  });
  return (
    <Card>
      <CardHeader title="Gap frequency" description="How many students have each gap across active drives." />
      <CardBody>
        <QueryState query={gaps}>
          {(rows) =>
            rows.length === 0 ? (
              <EmptyState title="No gap analyses yet" />
            ) : (
              <BarList
                title="Students per gap"
                max={Math.max(...rows.map((r) => r.students))}
                rows={rows.slice(0, 10).map((r) => ({
                  key: r.skill_id,
                  label: r.skill,
                  value: r.students,
                  display: `${r.students}`,
                  note: `${r.missing} no evidence · ${r.unverified} unverified only · ${r.high_impact} high impact`,
                  cluster: r.cluster ?? null,
                }))}
              />
            )
          }
        </QueryState>
      </CardBody>
    </Card>
  );
}

function Coverage() {
  const coverage = useQuery({
    queryKey: ["reports", "coverage"],
    queryFn: () => get<VerificationCoverage>("/api/v1/reports/verification-coverage/"),
  });
  return (
    <Card>
      <CardHeader title="Verification coverage" />
      <CardBody>
        <QueryState query={coverage}>
          {(c) => (
            <div className="flex flex-col gap-4">
              <StatGrid>
                <StatCard
                  label="Students with verified evidence"
                  value={`${c.student_coverage_percent}%`}
                  hint={`${c.students_with_verified_evidence} of ${c.students}`}
                />
                <StatCard label="Pending reviews" value={c.pending} />
              </StatGrid>
              <BarList
                title="Verified share by evidence type"
                rows={c.by_source.map((s) => ({
                  key: s.source_type,
                  label: s.source_type.replace(/_/g, " "),
                  value: s.percent_verified,
                  note: `${s.verified} of ${s.total} verified`,
                }))}
              />
            </div>
          )}
        </QueryState>
      </CardBody>
    </Card>
  );
}

function Departments() {
  const rows = useQuery({
    queryKey: ["reports", "departments"],
    queryFn: () => get<DepartmentRow[]>("/api/v1/reports/departments/"),
  });
  return (
    <Card>
      <CardHeader title="Department comparison" description="Institutional view (placement head)." />
      <QueryState query={rows}>
        {(list) => (
          <Table caption="Department comparison">
            <thead>
              <tr>
                <Th>Department</Th>
                <Th>Students</Th>
                <Th>Average readiness</Th>
                <Th>Ready (≥70%)</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((d) => (
                <tr key={d.department}>
                  <Td>
                    <span className="font-medium">{d.department}</span>
                    <span className="block text-xs text-muted">{d.name}</span>
                  </Td>
                  <Td className="tabular-nums">{d.students}</Td>
                  <Td className="tabular-nums">{pct(d.average_readiness, 1)}</Td>
                  <Td className="tabular-nums">{pct(d.ready_percent, 1)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </QueryState>
    </Card>
  );
}

function Training() {
  const t = useQuery({
    queryKey: ["reports", "training"],
    queryFn: () => get<TrainingEffectiveness>("/api/v1/reports/training-effectiveness/"),
  });
  const fmt = (v: number | null) => (v === null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)} pts`);
  return (
    <Card>
      <CardHeader
        title="Training effectiveness"
        description="Readiness change between each student's first and latest score."
      />
      <CardBody>
        <QueryState query={t}>
          {(x) =>
            x.students_with_history === 0 ? (
              <EmptyState title="Not enough history yet">
                Needs at least two readiness computations per student.
              </EmptyState>
            ) : (
              <div className="flex flex-col gap-3 text-sm">
                <StatGrid>
                  <StatCard
                    label="Followed their plan (≥50% done)"
                    value={fmt(x.plan_engaged.average_change)}
                    hint={`${x.plan_engaged.students} students`}
                  />
                  <StatCard
                    label="Others"
                    value={fmt(x.not_engaged.average_change)}
                    hint={`${x.not_engaged.students} students`}
                  />
                </StatGrid>
                <p className="text-xs text-muted">{x.note}</p>
              </div>
            )
          }
        </QueryState>
      </CardBody>
    </Card>
  );
}
