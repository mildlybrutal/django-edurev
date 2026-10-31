import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/components/shell/auth-layout";
import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Create your account" };

export default function SignupPage() {
  return (
    <AuthLayout
      wide
      title="Create your student account"
      description="Your placement cell confirms your academic details before drives rely on them."
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <SignupForm />
    </AuthLayout>
  );
}
