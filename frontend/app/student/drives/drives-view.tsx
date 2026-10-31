"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { PageHeader } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { QueryState } from "@/components/ui/states";
import { DriveStatusBadge, EligibilityBadge, RegistrationBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { get } from "@/lib/api/request";
import type { StudentDashboard } from "@/lib/api/types";
import { api, unwrap } from "@/lib/api/client";

export function DrivesView() {
  const drives = useQuery({
    queryKey: ["drives", "student"],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/")).results,
  });
  // Per-drive eligibility and match come from the dashboard aggregate (one request).
  const dashboard = useQuery({
    queryKey: ["dashboard", "student"],
    queryFn: () => get<StudentDashboard>("/api/v1/dashboard/student/"),
  });
  const byId = new Map(dashboard.data?.drives.map((d) => [d.id, d]));

  return (
    <>
      <PageHeader
        title="Placement Drives"
        description="Eligibility is about hard criteria; skill match and readiness are about your evidence. They are shown separately."
      />
      <Card>
        <QueryState query={drives}>
          {(list) =>
            list.length === 0 ? (
              <div className="p-5">
                <EmptyState title="No drives published yet" />
              </div>
            ) : (
              <Table caption="Placement drives">
                <thead>
                  <tr>
                    <Th>Company and role</Th>
                    <Th>Status</Th>
                    <Th>Drive date</Th>
                    <Th>Eligibility</Th>
                    <Th>Skill match</Th>
                    <Th>Registration</Th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((d) => {
                    const mine = byId.get(d.id);
                    return (
                      <tr key={d.id}>
                        <Td>
                          <Link href={`/student/drives/${d.id}`} className="font-medium hover:underline">
                            {d.company.name}
                          </Link>
                          <span className="block text-xs text-muted">
                            {d.role_title}
                            {d.location && ` · ${d.location}`}
                          </span>
                        </Td>
                        <Td>
                          <DriveStatusBadge status={d.status ?? ""} label={d.status_label} />
                        </Td>
                        <Td className="tabular-nums">{d.drive_date ?? "—"}</Td>
                        <Td>
                          {mine ? (
                            <EligibilityBadge eligible={mine.is_eligible} />
                          ) : (
                            <Link href={`/student/drives/${d.id}`} className="text-sm text-primary">
                              Check
                            </Link>
                          )}
                        </Td>
                        <Td className="tabular-nums">{mine ? `${mine.compatibility.toFixed(0)}%` : "—"}</Td>
                        <Td>
                          <RegistrationBadge status={mine?.registration?.status} />
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            )
          }
        </QueryState>
      </Card>
    </>
  );
}
