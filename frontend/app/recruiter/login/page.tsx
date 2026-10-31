import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/app/login/login-form";
import { AuthLayout } from "@/components/shell/auth-layout";

export const metadata: Metadata = { title: "Recruiter sign in" };

export default function RecruiterLoginPage() {
  return (
    <AuthLayout title="Recruiter portal" description="Sign in with the account the placement cell created for you.">
      <Suspense>
        <LoginForm portal="recruiter" />
      </Suspense>
    </AuthLayout>
  );
}
