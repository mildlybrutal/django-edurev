import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { HUE, hueFor } from "@/lib/modules";

/**
 * Signature element: a numbered module spine in the skill cluster's hue, on the left of a
 * gap, plan item or skill row. `next` marks the one step the student should take now, in the
 * reserved violet. The number is real sequence (rank / order), not decoration.
 */
export function ModuleRow({
  index,
  cluster,
  next = false,
  done = false,
  children,
  className,
}: {
  index: number;
  cluster: string | null | undefined;
  next?: boolean;
  done?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const hue = HUE[hueFor(cluster)];
  return (
    <div
      className={cn(
        "group flex min-w-0 items-stretch gap-0 overflow-hidden rounded-lg border bg-surface transition-[border-color,box-shadow] duration-150 ease-out",
        next ? "border-next" : "border-border hover:border-border-strong",
        className,
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "flex w-11 shrink-0 items-center justify-center text-sm font-semibold tabular-nums",
          done ? "bg-surface-muted text-muted" : cn(hue.solid, hue.ink),
        )}
      >
        {String(index).padStart(2, "0")}
      </div>
      <div className="min-w-0 flex-1 px-4 py-3">{children}</div>
    </div>
  );
}

/** "Next" tag in the reserved violet. Paired with text, never colour alone. */
export function NextTag({ children = "Next" }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded bg-next px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-next-foreground uppercase">
      {children}
    </span>
  );
}

/** Small cluster chip: hue swatch plus the cluster name. */
export function ClusterChip({ cluster, label }: { cluster: string | null | undefined; label?: string | null }) {
  const hue = HUE[hueFor(cluster)];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-xs font-medium", hue.soft, hue.text)}
    >
      <span aria-hidden="true" className={cn("size-2 rounded-sm", hue.solid)} />
      {label ?? cluster ?? "General"}
    </span>
  );
}
