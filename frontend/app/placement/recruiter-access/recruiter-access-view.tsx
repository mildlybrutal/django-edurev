"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";
import { del, get, post } from "@/lib/api/request";

type Field = { field: string; label: string };

export function RecruiterAccessView() {
  return (
    <>
      <PageHeader
        title="Recruiter Access"
        description="Recruiters see only students registered for a drive you grant, only the fields you release, until the grant expires. Every access is logged."
      />
      <div className="flex flex-col gap-5">
        <div className="grid gap-5 xl:grid-cols-2">
          <NewGrant />
          <Recruiters />
        </div>
        <Grants />
        <AccessLogs />
      </div>
    </>
  );
}

function Recruiters() {
  const queryClient = useQueryClient();
  const recruiters = useQuery({
    queryKey: ["recruiter-admin", "recruiters"],
    queryFn: async () => unwrap(await api.GET("/api/v1/recruiter-admin/recruiters/")),
  });
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", password: "" });
  const create = useMutation({
    meta: { toast: "Recruiter account created" },
    mutationFn: () => post("/api/v1/recruiter-admin/recruiters/", form),
    onSuccess: () => {
      setForm({ email: "", first_name: "", last_name: "", password: "" });
      queryClient.invalidateQueries({ queryKey: ["recruiter-admin"] });
    },
  });
  return (
    <Card>
      <CardHeader
        title="Recruiter accounts"
        description="Recruiters sign in at /recruiter/login, a separate portal with its own session."
      />
      <CardBody className="flex flex-col gap-4">
        <QueryState query={recruiters}>
          {(list) =>
            list.length === 0 ? (
              <p className="text-sm text-muted">No recruiter accounts yet.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {list.map((r) => (
                  <li key={r.id}>
                    {r.first_name} {r.last_name} <span className="text-muted">· {r.email}</span>
                  </li>
                ))}
              </ul>
            )
          }
        </QueryState>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <TextField
            label="First name"
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            required
          />
          <TextField
            label="Last name"
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
          />
          <TextField
            label="Email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <TextField
            label="Initial password (min 10 chars)"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
            minLength={10}
            autoComplete="new-password"
          />
          <div className="flex flex-col gap-2 sm:col-span-2">
            {create.error ? <FormError message={errorMessage(create.error)} /> : null}
            <Button type="submit" variant="secondary" className="self-start" disabled={create.isPending}>
              Create recruiter
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function NewGrant() {
  const queryClient = useQueryClient();
  const recruiters = useQuery({
    queryKey: ["recruiter-admin", "recruiters"],
    queryFn: async () => unwrap(await api.GET("/api/v1/recruiter-admin/recruiters/")),
  });
  const drives = useQuery({
    queryKey: ["drives", "cell", ""],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/")),
  });
  const fields = useQuery({
    queryKey: ["recruiter-admin", "fields"],
    queryFn: () => get<Field[]>("/api/v1/recruiter-admin/fields/"),
  });
  const [recruiter, setRecruiter] = useState("");
  const [drive, setDrive] = useState("");
  const [scope, setScope] = useState("registered");
  const [expires, setExpires] = useState("");
  const [allowed, setAllowed] = useState<string[]>([
    "name",
    "department",
    "graduation_year",
    "compatibility",
    "skills",
    "registration_status",
  ]);
  const create = useMutation({
    meta: { toast: "Access granted" },
    mutationFn: () =>
      post("/api/v1/recruiter-admin/grants/", {
        recruiter_id: Number(recruiter),
        drive_id: Number(drive),
        allowed_fields: allowed,
        candidate_scope: scope,
        expires_at: new Date(expires).toISOString(),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recruiter-admin"] }),
  });
  return (
    <Card>
      <CardHeader title="Grant access" description="Time-boxed, one drive, chosen fields only." />
      <CardBody>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <SelectField label="Recruiter" value={recruiter} onChange={(e) => setRecruiter(e.target.value)} required>
            <option value="">Choose…</option>
            {recruiters.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.email}
              </option>
            ))}
          </SelectField>
          <SelectField label="Drive" value={drive} onChange={(e) => setDrive(e.target.value)} required>
            <option value="">Choose…</option>
            {drives.data?.results
              .filter((d) => d.status !== "draft")
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.company.name} — {d.role_title}
                </option>
              ))}
          </SelectField>
          <SelectField label="Candidates" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="registered">All registered students</option>
            <option value="shortlisted">Shortlisted only</option>
          </SelectField>
          <TextField
            label="Expires"
            type="datetime-local"
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
            required
          />
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">Fields released</legend>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {fields.data?.map((f) => (
                <label key={f.field} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={allowed.includes(f.field)}
                    onChange={(e) =>
                      setAllowed(e.target.checked ? [...allowed, f.field] : allowed.filter((x) => x !== f.field))
                    }
                  />
                  {f.label}
                </label>
              ))}
            </div>
          </fieldset>
          {create.error ? <FormError message={errorMessage(create.error)} /> : null}
          <Button
            type="submit"
            className="self-start"
            disabled={create.isPending || !recruiter || !drive || !expires || allowed.length === 0}
          >
            Grant access
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function Grants() {
  const queryClient = useQueryClient();
  const grants = useQuery({
    queryKey: ["recruiter-admin", "grants"],
    queryFn: async () => unwrap(await api.GET("/api/v1/recruiter-admin/grants/")),
  });
  const revoke = useMutation({
    meta: { toast: "Access revoked" },
    mutationFn: (id: number) => del(`/api/v1/recruiter-admin/grants/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recruiter-admin"] }),
  });
  return (
    <Card>
      <CardHeader title="Grants" />
      <QueryState query={grants}>
        {(page) =>
          page.results.length === 0 ? (
            <CardBody>
              <EmptyState title="No grants yet" />
            </CardBody>
          ) : (
            <Table caption="Recruiter grants">
              <thead>
                <tr>
                  <Th>Recruiter</Th>
                  <Th>Drive</Th>
                  <Th>Fields</Th>
                  <Th>Scope</Th>
                  <Th>Valid until</Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {page.results.map((g) => (
                  <tr key={g.id}>
                    <Td>{g.recruiter_email}</Td>
                    <Td>{g.drive_label}</Td>
                    <Td className="max-w-xs text-xs text-muted">{g.allowed_fields.join(", ")}</Td>
                    <Td className="capitalize">{g.candidate_scope}</Td>
                    <Td className="tabular-nums">{new Date(g.expires_at).toLocaleString()}</Td>
                    <Td>
                      {g.is_valid ? (
                        <Badge tone="success">Active</Badge>
                      ) : (
                        <Badge>{g.status === "revoked" ? "Revoked" : "Expired / not started"}</Badge>
                      )}
                    </Td>
                    <Td>
                      {g.status === "active" && (
                        <Button variant="ghost" onClick={() => revoke.mutate(g.id)} disabled={revoke.isPending}>
                          Revoke
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )
        }
      </QueryState>
    </Card>
  );
}

function AccessLogs() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const logs = useQuery({
    queryKey: ["recruiter-admin", "logs", action, page],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/recruiter-admin/access-logs/", {
          params: { query: { action: action || undefined, page } },
        }),
      ),
  });
  return (
    <Card>
      <CardHeader
        title="Access log"
        description="Every recruiter list, search, profile view and denied attempt."
        action={
          <SelectField
            label="Action"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="list">List</option>
            <option value="search">Search</option>
            <option value="detail">Profile view</option>
            <option value="denied">Denied</option>
          </SelectField>
        }
      />
      <QueryState query={logs}>
        {(p) =>
          p.results.length === 0 ? (
            <CardBody>
              <EmptyState title="No recruiter access yet" />
            </CardBody>
          ) : (
            <>
              <Table caption="Recruiter access log">
                <thead>
                  <tr>
                    <Th>When</Th>
                    <Th>Recruiter</Th>
                    <Th>Action</Th>
                    <Th>Drive</Th>
                    <Th>Students</Th>
                    <Th>Fields released</Th>
                    <Th>IP</Th>
                  </tr>
                </thead>
                <tbody>
                  {p.results.map((l) => (
                    <tr key={l.id}>
                      <Td className="tabular-nums">{new Date(l.created_at).toLocaleString()}</Td>
                      <Td>{l.recruiter_email}</Td>
                      <Td>
                        {l.action === "denied" ? (
                          <Badge tone="danger">Denied</Badge>
                        ) : (
                          <span className="capitalize">{l.action}</span>
                        )}
                        {Object.keys(l.query ?? {}).length > 0 && (
                          <span className="block text-xs text-muted">{JSON.stringify(l.query)}</span>
                        )}
                      </Td>
                      <Td className="tabular-nums">{l.drive_id_requested ?? "—"}</Td>
                      <Td className="tabular-nums">{(l.student_ids as number[] | undefined)?.length ?? 0}</Td>
                      <Td className="text-xs text-muted">
                        {(l.fields_released as string[] | undefined)?.join(", ") || "—"}
                      </Td>
                      <Td className="text-xs text-muted">{l.ip ?? "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <div className="flex items-center justify-between px-5 py-2.5 text-sm">
                <span className="text-muted">{p.count} entries</span>
                <span className="flex gap-2">
                  <Button variant="ghost" disabled={!p.previous} onClick={() => setPage((x) => x - 1)}>
                    Previous
                  </Button>
                  <Button variant="ghost" disabled={!p.next} onClick={() => setPage((x) => x + 1)}>
                    Next
                  </Button>
                </span>
              </div>
            </>
          )
        }
      </QueryState>
    </Card>
  );
}
