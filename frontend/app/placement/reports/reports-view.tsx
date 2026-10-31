"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { BarList } from "@/components/charts/bar-list";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SelectField } from "@/components/ui/form";
import { QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";
import { get } from "@/lib/api/request";
import type { DemandAcrossDrives, Funnel, SupplyDemand } from "@/lib/api/types";

export function ReportsView() {
  const demand = useQuery({
    queryKey: ["reports", "demand"],
    queryFn: () => get<DemandAcrossDrives>("/api/v1/reports/demand/"),
  });
  const drives = useQuery({
    queryKey: ["drives", "cell", ""],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/")),
  });
  const [driveId, setDriveId] = useState("");
  const selected = driveId || String(drives.data?.results.find((d) => d.status !== "draft")?.id ?? "");
  return (
    <>
      <PageHeader
        title="Reports"
        description="Skill supply against drive demand tells the training team what to run next term."
      />
      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader
            title="Demand across active drives"
            description="Every skill an active drive requires, how many drives need it, and the share of students who meet the highest required level."
          />
          <QueryState query={demand}>
            {(d) =>
              d.skills.length === 0 ? (
                <CardBody>
                  <EmptyState title="No active drives with requirements" />
                </CardBody>
              ) : (
                <Table caption="Skill demand across active drives">
                  <thead>
                    <tr>
                      <Th>Skill</Th>
                      <Th>Active drives</Th>
                      <Th>Highest level required</Th>
                      <Th className="w-64">Students meeting it</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.skills.map((s) => (
                      <tr key={s.skill_id}>
                        <Td className="font-medium">{s.skill}</Td>
                        <Td className="tabular-nums">{s.active_drives}</Td>
                        <Td>{s.required_level}</Td>
                        <Td>
                          <BarList
                            title={`${s.skill} supply`}
                            rows={[{ key: s.skill_id, label: "", value: s.supply_percent }]}
                          />
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )
            }
          </QueryState>
        </Card>
        <Card>
          <CardHeader
            title="Supply vs demand for a drive"
            action={
              <SelectField label="Drive" value={selected} onChange={(e) => setDriveId(e.target.value)}>
                {drives.data?.results
                  .filter((d) => d.status !== "draft")
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.company.name} — {d.role_title}
                    </option>
                  ))}
              </SelectField>
            }
          />
          <CardBody>
            {selected ? <DriveSupply id={Number(selected)} /> : <EmptyState title="No published drives" />}
          </CardBody>
        </Card>
      </div>
    </>
  );
}

function DriveSupply({ id }: { id: number }) {
  const report = useQuery({
    queryKey: ["reports", "supply", id, "all"],
    queryFn: () => get<SupplyDemand>(`/api/v1/reports/drives/${id}/supply-demand/?population=all`),
  });
  const funnel = useQuery({
    queryKey: ["reports", "funnel", id],
    queryFn: () => get<Funnel>(`/api/v1/reports/drives/${id}/funnel/`),
  });
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <QueryState query={report}>
        {(r) => (
          <BarList
            title="Students meeting each requirement"
            rows={r.requirements.map((x) => ({
              key: x.skill_id,
              label: `${x.skill} (${x.required_level}+)`,
              value: x.supply_percent,
              cluster: x.cluster ?? null,
              note: `${x.verified_supply_percent}% verified · ${x.shortfall_students} students short · ${x.demand_share}% of drive weight`,
            }))}
          />
        )}
      </QueryState>
      <QueryState query={funnel}>
        {(f) => (
          <BarList
            title="Drive funnel"
            max={Math.max(1, f.stages[0]?.count ?? 1)}
            rows={f.stages.map((s) => ({ key: s.stage, label: s.stage, value: s.count, display: String(s.count) }))}
          />
        )}
      </QueryState>
    </div>
  );
}
