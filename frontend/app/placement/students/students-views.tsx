"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";
import { post } from "@/lib/api/request";

export function StudentsList() {
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: async () => unwrap(await api.GET("/api/v1/students/departments/")),
  });
  const students = useQuery({
    queryKey: ["students", q, department, page],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/students/", {
          params: { query: { q: q || undefined, department: department || undefined, page } },
        }),
      ),
  });
  return (
    <>
      <PageHeader
        title="Students"
        description="Academic records, skill profiles and readiness."
        actions={<Button onClick={() => setAdding((a) => !a)}>{adding ? "Close" : "Add student"}</Button>}
      />
      {adding && <AddStudent />}
      <Card>
        <div className="flex flex-wrap items-end gap-3 border-b border-border px-5 py-3">
          <TextField
            label="Search name, registration number or email"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="w-72"
          />
          <SelectField
            label="Department"
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.code}>
                {d.code}
              </option>
            ))}
          </SelectField>
        </div>
        <QueryState query={students}>
          {(p) =>
            p.results.length === 0 ? (
              <CardBody>
                <EmptyState title="No students found" />
              </CardBody>
            ) : (
              <>
                <Table caption="Students">
                  <thead>
                    <tr>
                      <Th>Student</Th>
                      <Th>Department</Th>
                      <Th>Year</Th>
                      <Th>CGPA</Th>
                      <Th>Backlogs</Th>
                      <Th>Mentor</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.results.map((s) => (
                      <tr key={s.id}>
                        <Td>
                          <Link href={`/placement/students/${s.id}`} className="font-medium hover:underline">
                            {s.name}
                          </Link>
                          <span className="block text-xs text-muted">
                            {s.roll_number} · {s.email}
                          </span>
                        </Td>
                        <Td>{s.department.code}</Td>
                        <Td className="tabular-nums">{s.graduation_year}</Td>
                        <Td className="tabular-nums">{s.cgpa}</Td>
                        <Td className="tabular-nums">{s.active_backlogs}</Td>
                        <Td>{s.mentor?.name ?? "—"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <div className="flex items-center justify-between px-5 py-2.5 text-sm">
                  <span className="text-muted">{p.count} students</span>
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
    </>
  );
}

function AddStudent() {
  const queryClient = useQueryClient();
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: async () => unwrap(await api.GET("/api/v1/students/departments/")),
  });
  const faculty = useQuery({
    queryKey: ["faculty"],
    queryFn: async () => unwrap(await api.GET("/api/v1/students/faculty/")),
  });
  const [form, setForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    roll_number: "",
    department_id: "",
    graduation_year: String(new Date().getFullYear() + 1),
    cgpa: "",
    active_backlogs: "0",
    mentor_id: "",
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const create = useMutation({
    meta: { toast: "Student added" },
    mutationFn: () =>
      post("/api/v1/students/", {
        ...form,
        department_id: Number(form.department_id),
        graduation_year: Number(form.graduation_year),
        active_backlogs: Number(form.active_backlogs),
        mentor_id: form.mentor_id ? Number(form.mentor_id) : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["students"] });
      setForm({ ...form, email: "", first_name: "", last_name: "", roll_number: "", cgpa: "" });
    },
  });
  return (
    <Card className="mb-5">
      <CardHeader
        title="Add a student"
        description="Normally imported from the ERP/SIS. The student signs in after an administrator sets their password."
      />
      <CardBody>
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <TextField label="First name" value={form.first_name} onChange={set("first_name")} required />
          <TextField label="Last name" value={form.last_name} onChange={set("last_name")} />
          <TextField label="Email" type="email" value={form.email} onChange={set("email")} required />
          <TextField
            label="Registration number"
            value={form.roll_number}
            onChange={set("roll_number")}
            required
            inputMode="numeric"
            pattern="[0-9]{8}"
            maxLength={8}
            placeholder="e.g. 12302221"
          />
          <SelectField label="Department" value={form.department_id} onChange={set("department_id")} required>
            <option value="">Choose…</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.code} — {d.name}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Graduation year"
            type="number"
            value={form.graduation_year}
            onChange={set("graduation_year")}
            required
          />
          <TextField
            label="CGPA"
            type="number"
            step="0.01"
            min={0}
            max={10}
            value={form.cgpa}
            onChange={set("cgpa")}
            required
          />
          <TextField
            label="Active backlogs"
            type="number"
            min={0}
            value={form.active_backlogs}
            onChange={set("active_backlogs")}
            required
          />
          <SelectField label="Mentor" value={form.mentor_id} onChange={set("mentor_id")}>
            <option value="">None</option>
            {faculty.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </SelectField>
          <div className="flex flex-col gap-2 md:col-span-3">
            {create.error ? <FormError message={errorMessage(create.error)} /> : null}
            {create.isSuccess && <p className="text-sm text-success">Student added.</p>}
            <Button type="submit" className="self-start" disabled={create.isPending}>
              Add student
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
