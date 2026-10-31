import { Suspense } from "react";
import { ShellFallback } from "@/components/shell/shell-fallback";
import { RecruiterShell } from "./recruiter-views";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<ShellFallback />}>
      <RecruiterShell>{children}</RecruiterShell>
    </Suspense>
  );
}
