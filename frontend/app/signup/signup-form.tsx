"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { FormError, SelectField } from "@/components/ui/form";
import { errorMessage, Loading } from "@/components/ui/states";
import { get, post } from "@/lib/api/request";
import { meQueryKey, type Me } from "@/lib/auth/session";

type Option = {
  code: string;
  name: string;
  email_domain: string;
  departments: { id: number; code: string; name: string }[];
};

const YEAR = new Date().getFullYear();

export function SignupForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const options = useQuery({
    queryKey: ["signup-options"],
    queryFn: () => get<Option[]>("/api/v1/auth/signup-options/"),
  });
  const [form, setForm] = useState({
    institution_code: "",
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    roll_number: "",
    department_id: "",
    graduation_year: String(YEAR + 1),
    cgpa: "",
    active_backlogs: "0",
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const signup = useMutation({
    mutationFn: (institution: string) =>
      post<Me>("/api/v1/auth/signup/", {
        ...form,
        institution_code: institution,
        department_id: Number(form.department_id),
        graduation_year: Number(form.graduation_year),
        active_backlogs: Number(form.active_backlogs),
      }),
    onSuccess: (me) => {
      qc.setQueryData(meQueryKey, me);
      // The onboarding pop-up opens on the dashboard.
      router.replace("/student");
    },
  });

  if (options.isPending) return <Loading />;
  const list = options.data ?? [];
  if (list.length === 0) {
    return (
      <p className="text-sm text-muted">
        Self sign-up is not open at your institution. Ask your placement cell for an account.
      </p>
    );
  }
  const institution = list.length === 1 ? list[0] : list.find((o) => o.code === form.institution_code);
  const domain = institution?.email_domain;
  const emailError =
    domain && form.email.includes("@") && !form.email.toLowerCase().endsWith(`@${domain}`)
      ? `Use your @${domain} address.`
      : undefined;
  const cgpa = Number(form.cgpa);
  const cgpaError = form.cgpa && (Number.isNaN(cgpa) || cgpa < 0 || cgpa > 10) ? "CGPA is on a 0–10 scale." : undefined;
  const regNoError =
    form.roll_number && !/^[0-9]{8}$/.test(form.roll_number) ? "Registration number is exactly 8 digits." : undefined;
  const ready =
    institution &&
    form.first_name &&
    form.email &&
    form.password.length >= 8 &&
    form.roll_number &&
    form.department_id &&
    form.cgpa &&
    !emailError &&
    !regNoError &&
    !cgpaError;

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      noValidate
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        if (ready && institution) signup.mutate(institution.code);
      }}
    >
      {list.length > 1 && (
        <SelectField
          label="Institution"
          className="sm:col-span-2"
          value={form.institution_code}
          onChange={set("institution_code")}
          required
        >
          <option value="">Choose your institution</option>
          {list.map((o) => (
            <option key={o.code} value={o.code}>
              {o.name}
            </option>
          ))}
        </SelectField>
      )}
      <TextField
        label="First name"
        autoComplete="given-name"
        required
        value={form.first_name}
        onChange={set("first_name")}
      />
      <TextField label="Last name" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} />
      <TextField
        label="College email"
        type="email"
        autoComplete="email"
        className="sm:col-span-2"
        placeholder={domain ? `you@${domain}` : "you@college.edu"}
        required
        value={form.email}
        error={emailError}
        onChange={set("email")}
      />
      <TextField
        label="Password"
        type="password"
        autoComplete="new-password"
        className="sm:col-span-2"
        required
        minLength={8}
        value={form.password}
        onChange={set("password")}
        error={form.password && form.password.length < 8 ? "At least 8 characters." : undefined}
      />
      <TextField
        label="Registration number"
        required
        inputMode="numeric"
        pattern="[0-9]{8}"
        maxLength={8}
        placeholder="e.g. 12302221"
        value={form.roll_number}
        onChange={set("roll_number")}
        error={regNoError}
      />
      <SelectField label="Department" required value={form.department_id} onChange={set("department_id")}>
        <option value="">Choose…</option>
        {institution?.departments.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </SelectField>
      <TextField
        label="Graduation year"
        type="number"
        inputMode="numeric"
        min={YEAR - 1}
        max={YEAR + 6}
        required
        value={form.graduation_year}
        onChange={set("graduation_year")}
      />
      <TextField
        label="Current CGPA"
        type="number"
        inputMode="decimal"
        step="0.01"
        min={0}
        max={10}
        required
        placeholder="8.20"
        value={form.cgpa}
        error={cgpaError}
        onChange={set("cgpa")}
      />
      <TextField
        label="Active backlogs"
        type="number"
        inputMode="numeric"
        min={0}
        required
        value={form.active_backlogs}
        onChange={set("active_backlogs")}
      />
      <p className="self-end text-xs text-muted sm:pb-2">
        CGPA and backlogs show as self-declared until the placement cell confirms them.
      </p>
      {signup.isError && (
        <div className="sm:col-span-2">
          <FormError message={errorMessage(signup.error)} />
        </div>
      )}
      <Button type="submit" className="sm:col-span-2" disabled={!ready || signup.isPending}>
        {signup.isPending ? "Creating account…" : "Create account"}
      </Button>
    </form>
  );
}
