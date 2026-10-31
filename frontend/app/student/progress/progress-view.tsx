"use client";

import { useQuery } from "@tanstack/react-query";
import { LineChart } from "@/components/charts/line-chart";
import { ReadinessPanel } from "@/components/domain/readiness-panel";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Meter } from "@/components/ui/meter";
import { QueryState } from "@/components/ui/states";
import { api, unwrap } from "@/lib/api/client";
import { get } from "@/lib/api/request";
import type { StudentReadiness } from "@/lib/api/types";

/** Readiness over time plus plan progress. `studentId` lets staff reuse the readiness part. */
export function ReadinessHistory({ studentId = "me" }: { studentId?: number | "me" }) {
  const readiness = useQuery({
    queryKey: ["readiness", studentId],
    queryFn: () => get<StudentReadiness>(`/api/v1/students/${studentId}/readiness/`),
  });
  return (
    <QueryState query={readiness}>
      {(r) => (
        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardHeader
              title="Readiness over time"
              description="Each point is a recomputation after new evidence or assessments."
            />
            <CardBody>
              {r.history.length < 2 ? (
                <EmptyState title="Not enough history yet">
                  The trend appears after your readiness has been computed twice.
                </EmptyState>
              ) : (
                <LineChart
                  title="Overall readiness over time"
                  points={r.history.map((h) => ({ at: h.at, value: h.overall }))}
                />
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Current readiness" />
            <CardBody>
              <ReadinessPanel snapshot={r.latest} threshold={r.ready_threshold} />
            </CardBody>
          </Card>
        </div>
      )}
    </QueryState>
  );
}

export function ProgressView() {
  const plans = useQuery({
    queryKey: ["plans", "all"],
    queryFn: async () => unwrap(await api.GET("/api/v1/preparation-plans/")).results,
  });
  return (
    <>
      <PageHeader title="Progress" description="How your readiness and preparation are moving." />
      <div className="flex flex-col gap-5">
        <ReadinessHistory />
        <Card>
          <CardHeader title="Preparation plans" />
          <QueryState query={plans}>
            {(list) =>
              list.length === 0 ? (
                <CardBody>
                  <EmptyState title="No plans yet" />
                </CardBody>
              ) : (
                <ul className="divide-y divide-border">
                  {list.map((p) => {
                    const progress = p.progress as { done: number; total: number; percent: number };
                    return (
                      <li key={p.id} className="flex flex-wrap items-center gap-4 px-5 py-3 text-sm">
                        <span className="min-w-48 flex-1 font-medium">
                          {p.title}
                          <span className="block text-xs font-normal text-muted capitalize">
                            {p.status} · {p.start_date} → {p.end_date}
                          </span>
                        </span>
                        <span className="w-48">
                          <Meter value={progress.percent} label={`${p.title} progress`} />
                        </span>
                        <span className="tabular-nums">
                          {progress.done}/{progress.total}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )
            }
          </QueryState>
        </Card>
      </div>
    </>
  );
}
