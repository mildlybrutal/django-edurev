"use client";

import { useState } from "react";

export type RadarAxis = { key: string; label: string; value: number };

/**
 * Single-series radar of readiness dimensions (P06 §8). One blue series, so no legend; each
 * vertex has a hover/focus tooltip, and the values are also listed beside it as text.
 */
export function RadarChart({ axes, size = 240, title }: { axes: RadarAxis[]; size?: number; title: string }) {
  const [active, setActive] = useState<string | null>(null);
  // Horizontal room for axis labels on both sides, so "Project depth" etc. are never clipped.
  const labelRoom = 84;
  const width = size + 2 * labelRoom;
  const c = size / 2;
  const cx = width / 2;
  const r = size / 2 - 28;
  const angle = (i: number) => -Math.PI / 2 + (2 * Math.PI * i) / axes.length;
  const point = (i: number, v: number) => {
    const rad = (r * Math.max(0, Math.min(100, v))) / 100;
    return [cx + rad * Math.cos(angle(i)), c + rad * Math.sin(angle(i))] as const;
  };
  const polygon = axes.map((a, i) => point(i, a.value).join(",")).join(" ");
  const activeAxis = axes.find((a) => a.key === active);

  return (
    <figure className="flex flex-wrap items-center gap-6">
      <div className="relative">
        <svg
          width={width}
          height={size}
          viewBox={`0 0 ${width} ${size}`}
          role="img"
          aria-label={title}
          className="max-w-full"
        >
          {[25, 50, 75, 100].map((ring) => (
            <polygon
              key={ring}
              points={axes.map((_, i) => point(i, ring).join(",")).join(" ")}
              fill="none"
              stroke="var(--grid)"
              strokeWidth={1}
            />
          ))}
          {axes.map((a, i) => {
            const [x, y] = point(i, 100);
            const [lx, ly] = [cx + (r + 12) * Math.cos(angle(i)), c + (r + 14) * Math.sin(angle(i))];
            return (
              <g key={a.key}>
                <line x1={cx} y1={c} x2={x} y2={y} stroke="var(--grid)" strokeWidth={1} />
                <text
                  x={lx}
                  y={ly}
                  textAnchor={Math.abs(lx - cx) < 4 ? "middle" : lx > cx ? "start" : "end"}
                  dominantBaseline="middle"
                  className="fill-muted text-[11px]"
                >
                  {a.label}
                </text>
              </g>
            );
          })}
          <polygon
            points={polygon}
            className="animate-radar-in"
            fill="var(--series-1)"
            fillOpacity={0.12}
            stroke="var(--series-1)"
            strokeWidth={2}
            strokeLinejoin="round"
          />
          {axes.map((a, i) => {
            const [x, y] = point(i, a.value);
            return (
              <g key={a.key}>
                <circle cx={x} cy={y} r={5} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
                {/* Larger invisible hit target for hover and keyboard focus. */}
                <circle
                  cx={x}
                  cy={y}
                  r={14}
                  fill="transparent"
                  tabIndex={0}
                  role="img"
                  aria-label={`${a.label}: ${a.value.toFixed(0)}%`}
                  onMouseEnter={() => setActive(a.key)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={() => setActive(a.key)}
                  onBlur={() => setActive(null)}
                />
              </g>
            );
          })}
        </svg>
        {activeAxis && (
          <div className="pointer-events-none absolute top-1 left-1 animate-pop-in rounded-md border border-border bg-surface-raised px-2 py-1 text-xs shadow-pop">
            <span className="text-muted">{activeAxis.label}</span>{" "}
            <span className="font-semibold tabular-nums">{activeAxis.value.toFixed(0)}%</span>
          </div>
        )}
      </div>
      <figcaption>
        <dl className="grid grid-cols-[auto_auto] gap-x-6 gap-y-1.5 text-sm">
          {axes.map((a) => (
            <div key={a.key} className="contents">
              <dt className="text-muted">{a.label}</dt>
              <dd className="text-right font-medium tabular-nums">{a.value.toFixed(0)}%</dd>
            </div>
          ))}
        </dl>
      </figcaption>
    </figure>
  );
}

export function readinessAxes(r: {
  technical: number;
  aptitude: number;
  communication: number;
  project_depth: number;
  coding_activity?: number;
}): RadarAxis[] {
  const axes = [
    { key: "technical", label: "Technical mastery", value: r.technical },
    { key: "aptitude", label: "Aptitude", value: r.aptitude },
    { key: "communication", label: "Communication", value: r.communication },
    { key: "project_depth", label: "Project depth", value: r.project_depth },
  ];
  // Snapshots computed before the coding-activity dimension existed have no value for it.
  if (r.coding_activity !== undefined)
    axes.push({ key: "coding_activity", label: "Coding activity", value: r.coding_activity });
  return axes;
}
