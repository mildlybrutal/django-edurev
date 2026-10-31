"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { DriveStatusBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";
import { post } from "@/lib/api/request";

export function DrivesList() {
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const drives = useQuery({
    queryKey: ["drives", "cell", status],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/drives/", { params: { query: { status: status || undefined } } })),
  });
  return (
    <>
      <PageHeader
        title="Placement Drives"
        description="Create a drive, paste the company's JD, map requirements, set eligibility and publish."
        actions={<Button onClick={() => setCreating((c) => !c)}>{creating ? "Close" : "New drive"}</Button>}
      />
      {creating && <NewDrive />}
      <Card>
        <CardHeader
          title="Drives"
          action={
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">Status</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="h-8 rounded-md border border-border bg-surface px-2"
              >
                <option value="">All</option>
                <option value="draft">Draft</option>
                <option value="published">Published</option>
                <option value="registration_closed">Registration closed</option>
                <option value="shortlisting">Shortlisting</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
          }
        />
        <QueryState query={drives}>
          {(page) =>
            page.results.length === 0 ? (
              <CardBody>
                <EmptyState title="No drives" />
              </CardBody>
            ) : (
              <Table caption="Drives">
                <thead>
                  <tr>
                    <Th>Company and role</Th>
                    <Th>Status</Th>
                    <Th>JD</Th>
                    <Th>Requirements</Th>
                    <Th>Registration closes</Th>
                    <Th>Drive date</Th>
                  </tr>
                </thead>
                <tbody>
                  {page.results.map((d) => (
                    <tr key={d.id}>
                      <Td>
                        <Link href={`/placement/drives/${d.id}`} className="font-medium hover:underline">
                          {d.company.name}
                        </Link>
                        <span className="block text-xs text-muted">{d.role_title}</span>
                      </Td>
                      <Td>
                        <DriveStatusBadge status={d.status ?? ""} label={d.status_label} />
                      </Td>
                      <Td className="text-sm capitalize">{(d.jd_status ?? "none").replace(/_/g, " ")}</Td>
                      <Td className="tabular-nums">{d.requirements.length}</Td>
                      <Td className="tabular-nums">
                        {d.registration_closes_at ? new Date(d.registration_closes_at).toLocaleDateString() : "—"}
                      </Td>
                      <Td className="tabular-nums">{d.drive_date ?? "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )
          }
        </QueryState>
      </Card>
    </>
  );
}

function NewDrive() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const companies = useQuery({
    queryKey: ["companies"],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/companies/")).results,
  });
  const roles = useQuery({
    queryKey: ["taxonomy", "roles"],
    queryFn: async () => unwrap(await api.GET("/api/v1/skills/roles/")).results,
  });
  const [companyId, setCompanyId] = useState("");
  const [newCompany, setNewCompany] = useState("");
  const [role, setRole] = useState("");
  const [template, setTemplate] = useState("");
  const [location, setLocation] = useState("");
  const [compensation, setCompensation] = useState("");
  const [opens, setOpens] = useState("");
  const [closes, setCloses] = useState("");
  const [driveDate, setDriveDate] = useState("");
  const create = useMutation({
    meta: { toast: "Drive created" },
    mutationFn: async () => {
      let company = Number(companyId);
      if (!company) company = (await post<{ id: number }>("/api/v1/drives/companies/", { name: newCompany })).id;
      return post<{ id: number }>("/api/v1/drives/", {
        company_id: company,
        role_title: role,
        target_role_id: template ? Number(template) : null,
        location,
        compensation,
        registration_opens_at: opens ? new Date(opens).toISOString() : null,
        registration_closes_at: closes ? new Date(closes).toISOString() : null,
        drive_date: driveDate || null,
      });
    },
    onSuccess: (drive) => {
      queryClient.invalidateQueries({ queryKey: ["drives"] });
      router.push(`/placement/drives/${drive.id}`);
    },
  });
  return (
    <Card className="mb-5">
      <CardHeader title="New drive" description="Starts as a draft. Students can't see it until you publish." />
      <CardBody>
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <SelectField label="Company" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">New company…</option>
            {companies.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </SelectField>
          {!companyId && (
            <TextField
              label="New company name"
              value={newCompany}
              onChange={(e) => setNewCompany(e.target.value)}
              required
            />
          )}
          <TextField label="Role title" value={role} onChange={(e) => setRole(e.target.value)} required />
          <SelectField
            label="Start requirements from a role template (optional)"
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
          >
            <option value="">None — I&apos;ll paste a JD</option>
            {roles.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </SelectField>
          <TextField label="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
          <TextField label="Compensation" value={compensation} onChange={(e) => setCompensation(e.target.value)} />
          <TextField
            label="Registration opens"
            type="datetime-local"
            value={opens}
            onChange={(e) => setOpens(e.target.value)}
          />
          <TextField
            label="Registration closes"
            type="datetime-local"
            value={closes}
            onChange={(e) => setCloses(e.target.value)}
          />
          <TextField label="Drive date" type="date" value={driveDate} onChange={(e) => setDriveDate(e.target.value)} />
          <div className="md:col-span-2 flex flex-col gap-2">
            {create.error ? <FormError message={errorMessage(create.error)} /> : null}
            <Button
              type="submit"
              className="self-start"
              disabled={create.isPending || !role || (!companyId && !newCompany)}
            >
              Create draft drive
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
