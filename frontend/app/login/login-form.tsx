"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { errorMessage } from "@/components/ui/states";
import { homeFor } from "@/lib/auth/roles";
import { useLogin, useVerifyMfa, type AuthPortal, type Me } from "@/lib/auth/session";

/** Only follow same-site relative paths after login, never an absolute URL. */
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

export function LoginForm({ portal = "internal" }: { portal?: AuthPortal }) {
  const router = useRouter();
  const params = useSearchParams();
  const login = useLogin(portal);
  const verify = useVerifyMfa(portal);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"password" | "code">("password");

  function done(me: Me) {
    const fallback = portal === "recruiter" ? "/recruiter" : homeFor(me.roles);
    router.replace(safeNext(params.get("next")) ?? fallback);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step === "password") {
      login.mutate(
        { email, password },
        { onSuccess: (outcome) => (outcome.kind === "mfa_required" ? setStep("code") : done(outcome.me)) },
      );
    } else {
      verify.mutate(code.trim(), { onSuccess: done });
    }
  }

  const error = step === "password" ? login.error : verify.error;
  const pending = login.isPending || verify.isPending;

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {step === "password" ? (
        <>
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </>
      ) : (
        <>
          <p className="text-sm text-muted">Enter the 6-digit code from your authenticator app.</p>
          <TextField
            label="Authentication code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]*"
            maxLength={6}
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
          {errorMessage(error)}
        </p>
      )}
      <Button
        type="submit"
        disabled={pending || (step === "password" ? !email || !password : code.trim().length !== 6)}
      >
        {pending ? "Signing in…" : step === "password" ? "Sign in" : "Verify"}
      </Button>
    </form>
  );
}
