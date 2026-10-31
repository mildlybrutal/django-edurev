import { Suspense } from "react";
import { PortalShell } from "@/components/shell/portal-shell";
import { ShellFallback } from "@/components/shell/shell-fallback";

export default function Layout({ children }: LayoutProps<"/faculty">) {
  // The shell reads the URL and session at request time, so it streams in behind a boundary.
  return (
    <Suspense fallback={<ShellFallback />}>
      <PortalShell portal="faculty">{children}</PortalShell>
    </Suspense>
  );
}
