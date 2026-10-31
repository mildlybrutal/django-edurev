"use client";

import { useState } from "react";

export type LinePoint = { at: string; value: number };

/** Single-series 0–100% line with a crosshair tooltip (dataviz: 2px line, 8px end marker). */
export function LineChart({ points, title, height = 180 }: { points: LinePoint[]; title: string; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 560;
  const pad = { l: 36, r: 16, t: 12, b: 24 };
  const w = width - pad.l - pad.r;
  const h = height - pad.t - pad.b;
  if (points.length === 0) return null;
  const x = (i: number) => pad.l + (points.length === 1 ? w / 2 : (w * i) / (points.length - 1));
  const y = (v: number) => pad.t + h - (h * Math.max(0, Math.min(100, v))) / 100;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
  const last = points.length - 1;
  const fmt = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    const rel = ((e.clientX - box.left) / box.width) * width - pad.l;
    const i = points.length === 1 ? 0 : Math.round((rel / w) * (points.length - 1));
    setHover(Math.max(0, Math.min(last, i)));
  }

  return (
    <div className="relative w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[320px]" role="img" aria-label={title}>
        {[0, 50, 100].map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={width - pad.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
            <text x={pad.l - 6} y={y(t)} textAnchor="end" dominantBaseline="middle" className="fill-muted text-[11px]">
              {t}%
            </text>
          </g>
        ))}
        <text x={x(0)} y={height - 6} className="fill-muted text-[11px]">
          {fmt(points[0].at)}
        </text>
        {last > 0 && (
          <text x={x(last)} y={height - 6} textAnchor="end" className="fill-muted text-[11px]">
            {fmt(points[last].at)}
          </text>
        )}
        <path
          d={path}
          fill="none"
          stroke="var(--series-1)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={x(last)}
          cy={y(points[last].value)}
          r={4}
          fill="var(--series-1)"
          stroke="var(--surface)"
          strokeWidth={2}
        />
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + h} stroke="var(--muted)" strokeWidth={1} />
            <circle
              cx={x(hover)}
              cy={y(points[hover].value)}
              r={4}
              fill="var(--series-1)"
              stroke="var(--surface)"
              strokeWidth={2}
            />
          </g>
        )}
        <rect
          x={pad.l}
          y={pad.t}
          width={w}
          height={h}
          fill="transparent"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        />
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-0 right-0 rounded-md border border-border bg-surface px-2 py-1 text-xs shadow-sm">
          <span className="text-muted">{fmt(points[hover].at)}</span>{" "}
          <span className="font-semibold tabular-nums">{points[hover].value.toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}
