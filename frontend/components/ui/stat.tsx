import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { HUE, type ModuleHue } from "@/lib/modules";

/** KPI tile: sentence-case label, one tabular value, optional hint. A thin hue band on top
 * ties the tile to its module colour. */
export function StatCard({
  label,
  value,
  hint,
  hue = "cobalt",
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  hue?: ModuleHue;
  icon?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-surface px-5 pt-5 pb-4">
      <span aria-hidden="true" className={cn("absolute inset-x-0 top-0 h-1", HUE[hue].solid)} />
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted">{label}</p>
        {icon && <span className={cn("shrink-0", HUE[hue].text)}>{icon}</span>}
      </div>
      <p className="mt-1.5 text-[1.75rem] leading-none font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

/** Percentage or an explicit "no data" marker — never a made-up number. */
export function pct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}
