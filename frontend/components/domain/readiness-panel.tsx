"use client";

import { ChevronDown } from "lucide-react";
import { RadarChart, readinessAxes } from "@/components/charts/radar";
import { EmptyState } from "@/components/ui/empty-state";
import { ReadyBadge } from "@/components/ui/status";
import type { DimensionExplanation, Snapshot } from "@/lib/api/types";

const LABELS: Record<string, string> = {
  technical: "Technical mastery",
  aptitude: "Aptitude",
  communication: "Communication",
  project_depth: "Project depth",
  coding_activity: "Coding activity",
};

/** Readiness as dimensions with an explanation of every score (never an opaque number). */
export function ReadinessPanel({ snapshot, threshold }: { snapshot: Snapshot | null; threshold: number }) {
  if (!snapshot) {
    return <EmptyState title="No readiness yet">It is computed from your evidence and assessments.</EmptyState>;
  }
  const dims = snapshot.explanation.dimensions;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="text-3xl font-semibold tabular-nums">{snapshot.overall.toFixed(0)}%</span>
        <span className="text-sm text-muted">overall readiness</span>
        <ReadyBadge ready={snapshot.overall >= threshold} />
        <span className="text-xs text-muted">
          Ready at {threshold}% · scoring v{snapshot.config_version}
        </span>
      </div>
      <RadarChart title="Readiness by dimension" axes={readinessAxes(snapshot)} />
      <div className="flex flex-col gap-2">
        {(Object.keys(LABELS) as (keyof typeof dims)[])
          .filter((key) => dims[key])
          .map((key) => (
            <DimensionDetail
              key={key}
              label={LABELS[key]}
              weight={snapshot.explanation.weights[key] ?? 0}
              dim={dims[key]}
            />
          ))}
      </div>
      <p className="text-xs text-muted">{snapshot.explanation.note}</p>
    </div>
  );
}

function DimensionDetail({ label, weight, dim }: { label: string; weight: number; dim: DimensionExplanation }) {
  return (
    <details className="group rounded-md border border-border px-3 py-2 text-sm transition-colors open:bg-surface-muted hover:border-border-strong">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <span>
          <span className="font-medium">{label}</span> <span className="text-xs text-muted">weight {weight}</span>
        </span>
        <span className="flex items-center gap-2 font-medium tabular-nums">
          {dim.score.toFixed(0)}%
          <ChevronDown
            aria-hidden="true"
            className="size-4 text-muted transition-transform duration-200 ease-out group-open:rotate-180"
          />
        </span>
      </summary>
      <p className="mt-2 text-muted">{dim.summary}</p>
      {dim.missing && <p className="mt-1 text-warning">{dim.missing}</p>}
      {dim.inputs.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 text-xs">
          {dim.inputs.map((input, i) => (
            <li key={i} className="flex flex-wrap gap-x-3">
              {Object.entries(input).map(([k, v]) => (
                <span key={k}>
                  <span className="text-muted">{k.replace(/_/g, " ")}:</span> {String(v ?? "—")}
                </span>
              ))}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
