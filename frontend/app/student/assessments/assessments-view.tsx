"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";

/** Assessment and mock-interview history. `studentId` lets staff reuse the view for a student. */
export function AssessmentHistory({ studentId, showHeader = true }: { studentId?: number; showHeader?: boolean }) {
  const assessments = useQuery({
    queryKey: ["assessments", studentId ?? "me"],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/assessments/", { params: { query: { student: studentId } } })).results,
  });
  const interviews = useQuery({
    queryKey: ["mock-interviews", studentId ?? "me"],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/assessments/mock-interviews/", { params: { query: { student: studentId } } }))
        .results,
  });
  return (
    <>
      {showHeader && (
        <PageHeader
          title="Assessments"
          description="Rubric-based assessments and mock interviews recorded by your mentor or the placement cell."
        />
      )}
      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader title="Assessments" />
          <QueryState query={assessments}>
            {(rows) =>
              rows.length === 0 ? (
                <div className="p-5">
                  <EmptyState title="No assessments recorded yet" />
                </div>
              ) : (
                <Table caption="Assessment history">
                  <thead>
                    <tr>
                      <Th>Date</Th>
                      <Th>Assessment</Th>
                      <Th>Type</Th>
                      <Th>Score</Th>
                      <Th>Criteria</Th>
                      <Th>Assessed by</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((a) => (
                      <tr key={a.id}>
                        <Td className="tabular-nums">{a.assessed_on}</Td>
                        <Td>
                          <span className="font-medium">{a.title}</span>
                          {a.skill && <span className="block text-xs text-muted">{a.skill}</span>}
                        </Td>
                        <Td className="capitalize">{a.kind}</Td>
                        <Td className="tabular-nums">{Number(a.percentage).toFixed(0)}%</Td>
                        <Td className="text-xs text-muted">
                          {a.scores.map((s) => `${s.criterion} ${s.score}/${s.max}`).join(" · ")}
                        </Td>
                        <Td>{a.assessed_by}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )
            }
          </QueryState>
        </Card>
        <Card>
          <CardHeader title="Mock interviews" />
          <QueryState query={interviews}>
            {(rows) =>
              rows.length === 0 ? (
                <div className="p-5">
                  <EmptyState title="No mock interviews yet" />
                </div>
              ) : (
                <Table caption="Mock interview history">
                  <thead>
                    <tr>
                      <Th>Date</Th>
                      <Th>Focus</Th>
                      <Th>Technical</Th>
                      <Th>Communication</Th>
                      <Th>Problem solving</Th>
                      <Th>Feedback</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((m) => (
                      <tr key={m.id}>
                        <Td className="tabular-nums">{m.conducted_on}</Td>
                        <Td>
                          {m.role_focus || "—"}
                          <span className="block text-xs text-muted">{m.interviewer}</span>
                        </Td>
                        <Td className="tabular-nums">{m.technical_score}%</Td>
                        <Td className="tabular-nums">{m.communication_score}%</Td>
                        <Td className="tabular-nums">{m.problem_solving_score}%</Td>
                        <Td className="max-w-sm text-muted">{m.feedback || "—"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )
            }
          </QueryState>
        </Card>
      </div>
    </>
  );
}
