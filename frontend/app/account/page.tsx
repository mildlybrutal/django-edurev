"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { PortalShell } from "@/components/shell/portal-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import { FormError, FormSuccess } from "@/components/ui/form";
import { errorMessage } from "@/components/ui/states";
import { post } from "@/lib/api/request";
import { meQueryKey, useMe, type Me } from "@/lib/auth/session";

export default function AccountPage() {
  return (
    <Suspense>
      <PortalShell portal="any">
        <Account />
      </PortalShell>
    </Suspense>
  );
}

function Account() {
  const { data: me } = useMe();
  if (!me) return null;
  return (
    <>
      <PageHeader title="Account" description="Your sign-in details and security settings." />
      {me.mfa.setup_required && (
        <p role="alert" className="mb-5 rounded-md bg-warning-soft px-4 py-3 text-sm text-warning">
          Your role requires two-factor authentication. Set it up below to continue using the platform.
        </p>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Profile" />
          <CardBody className="text-sm">
            <dl className="grid grid-cols-[8rem_1fr] gap-y-2">
              <dt className="text-muted">Name</dt>
              <dd>{`${me.first_name} ${me.last_name}`.trim() || "—"}</dd>
              <dt className="text-muted">Email</dt>
              <dd>{me.email}</dd>
              <dt className="text-muted">Roles</dt>
              <dd className="flex flex-wrap gap-1">
                {me.roles.map((r) => (
                  <Badge key={r}>{r.replace(/_/g, " ")}</Badge>
                ))}
              </dd>
              <dt className="text-muted">Institution</dt>
              <dd>{me.institution?.name ?? "—"}</dd>
            </dl>
          </CardBody>
        </Card>
        <TwoFactorCard me={me} />
      </div>
    </>
  );
}

function TwoFactorCard({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const refresh = (next: Me) => queryClient.setQueryData(meQueryKey, next);

  const start = useMutation({
    mutationFn: () => post<{ secret: string; otpauth_uri: string }>("/api/v1/auth/mfa/setup/"),
    onSuccess: (data) => {
      setSetup(data);
      setDone(null);
    },
  });
  const confirm = useMutation({
    meta: { toast: "Two-factor authentication is on" },
    mutationFn: (value: string) => post<Me>("/api/v1/auth/mfa/confirm/", { code: value }),
    onSuccess: (next) => {
      refresh(next);
      setSetup(null);
      setCode("");
      setDone("Two-factor authentication is on. You'll be asked for a code when you sign in.");
    },
  });
  const disable = useMutation({
    meta: { toast: "Two-factor authentication is off" },
    mutationFn: (value: string) => post<Me>("/api/v1/auth/mfa/disable/", { code: value }),
    onSuccess: (next) => {
      refresh(next);
      setCode("");
      setDone("Two-factor authentication is off.");
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (setup) confirm.mutate(code.trim());
    else disable.mutate(code.trim());
  }

  return (
    <Card>
      <CardHeader
        title="Two-factor authentication"
        description="A time-based code from an authenticator app (TOTP)."
        action={me.mfa.enabled ? <Badge tone="success">On</Badge> : <Badge>Off</Badge>}
      />
      <CardBody className="flex flex-col gap-4 text-sm">
        <FormSuccess message={done} />
        {!me.mfa.enabled && !setup && (
          <>
            <p className="text-muted">
              Add this account to an authenticator app such as Google Authenticator, Microsoft Authenticator or
              1Password, then confirm with a code.
            </p>
            <Button onClick={() => start.mutate()} disabled={start.isPending} className="self-start">
              Set up two-factor authentication
            </Button>
            {start.error ? <FormError message={errorMessage(start.error)} /> : null}
          </>
        )}
        {setup && (
          <div className="flex flex-col gap-3">
            <p>In your authenticator app, add an account using this setup key (time-based, 6 digits, 30 seconds):</p>
            <code className="rounded-md bg-surface-muted px-3 py-2 font-mono text-sm break-all select-all">
              {setup.secret.match(/.{1,4}/g)?.join(" ")}
            </code>
            <details className="text-xs text-muted">
              <summary className="cursor-pointer">Setup link (for apps that accept otpauth links)</summary>
              <code className="mt-1 block font-mono break-all select-all">{setup.otpauth_uri}</code>
            </details>
          </div>
        )}
        {(setup || me.mfa.enabled) && (
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <TextField
              label={setup ? "Code from your app" : "Code to turn two-factor off"}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            {confirm.error ? <FormError message={errorMessage(confirm.error)} /> : null}
            {disable.error ? <FormError message={errorMessage(disable.error)} /> : null}
            {setup ? (
              <Button type="submit" disabled={code.trim().length !== 6 || confirm.isPending} className="self-start">
                Confirm and turn on
              </Button>
            ) : (
              !me.mfa.setup_required && (
                <Button
                  type="submit"
                  variant="danger"
                  disabled={code.trim().length !== 6 || disable.isPending}
                  className="self-start"
                >
                  Turn off
                </Button>
              )
            )}
          </form>
        )}
      </CardBody>
    </Card>
  );
}
