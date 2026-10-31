import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { HUE, hueFor } from "@/lib/modules";

export type BarRow = {
  key: string | number;
  label: ReactNode;
  value: number;
  display?: string;
  note?: ReactNode;
  /** Skill cluster: colours the bar in its module hue and adds a swatch to the label. */
  cluster?: string | null;
};

/**
 * Horizontal bars for one measure (0–100 unless `max` is given). Labels and values are text in
 * ink colours; the bar alone carries the blue. Each row has a native tooltip.
 */
export function BarList({ rows, max = 100, title }: { rows: BarRow[]; max?: number; title: string }) {
  return (
    <ul aria-label={title} className="flex flex-col gap-3">
      {rows.map((row) => {
        const width = max > 0 ? Math.max(0, Math.min(100, (100 * row.value) / max)) : 0;
        const display = row.display ?? `${row.value.toFixed(0)}%`;
        return (
          <li key={row.key} title={`${typeof row.label === "string" ? row.label : ""} ${display}`.trim()}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                {row.cluster !== undefined && (
                  <span
                    aria-hidden="true"
                    className={cn("size-2.5 shrink-0 rounded-sm", HUE[hueFor(row.cluster)].solid)}
                  />
                )}
                <span className="truncate">{row.label}</span>
              </span>
              <span className="shrink-0 font-medium tabular-nums">{display}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-series-track">
              <div
                className={cn(
                  "h-2 origin-left animate-meter rounded-full",
                  row.cluster !== undefined ? HUE[hueFor(row.cluster)].bar : "bg-series-1",
                )}
                style={{ width: `${width}%` }}
              />
            </div>
            {row.note && <div className="mt-1 text-xs text-muted">{row.note}</div>}
          </li>
        );
      })}
    </ul>
  );
}

/** Column chart for a small ordered distribution (e.g. readiness bands). */
export function Columns({
  rows,
  title,
}: {
  rows: { label: string; count: number; percent?: number }[];
  title: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  const plot = 128; // px available for the tallest column
  return (
    <figure>
      <div role="img" aria-label={title} className="flex h-40 items-end gap-4 border-b border-grid px-2">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex flex-1 flex-col items-center justify-end gap-1"
            title={`${r.label}: ${r.count}`}
          >
            <span className="text-xs font-medium tabular-nums">{r.count}</span>
            <div
              className="w-full max-w-6 rounded-t bg-series-1"
              style={{ height: `${Math.round((plot * r.count) / max)}px`, minHeight: r.count ? 2 : 0 }}
            />
          </div>
        ))}
      </div>
      <figcaption className="flex gap-4 px-2 pt-1.5">
        {rows.map((r) => (
          <span key={r.label} className="flex-1 text-center text-xs text-muted">
            {r.label}
            {r.percent !== undefined && <span className="block tabular-nums">{r.percent}%</span>}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
