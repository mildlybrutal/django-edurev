import { CalendarClock } from "lucide-react";
import { cn } from "@/lib/cn";

const DAY = 86_400_000;

function days(from: string, to: string) {
  return Math.round((Date.parse(to) - Date.parse(from)) / DAY);
}

/**
 * The plan's hard time budget: how much of the window to the drive has passed against how much
 * of the work is done. Behind schedule when time used runs ahead of work done.
 */
export function TimeBudget({
  start,
  end,
  driveDate,
  done,
  total,
  company,
  className,
}: {
  start: string;
  end: string;
  driveDate?: string | null;
  done: number;
  total: number;
  company?: string | null;
  className?: string;
}) {
  const target = driveDate ?? end;
  const today = new Date().toISOString().slice(0, 10);
  const span = Math.max(1, days(start, target));
  const used = Math.max(0, Math.min(span, days(start, today)));
  const left = Math.max(0, days(today, target));
  const timePct = Math.round((100 * used) / span);
  const workPct = total ? Math.round((100 * done) / total) : 0;
  const behind = total > 0 && done < total && timePct > workPct + 10;
  return (
    <div className={cn("rounded-lg border border-border bg-surface px-4 py-3.5", className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          <CalendarClock aria-hidden="true" className="size-4 text-muted" strokeWidth={1.75} />
          {left === 0 ? "Drive day" : `${left} day${left === 1 ? "" : "s"} left`}
          <span className="font-normal text-muted">
            {driveDate ? `until ${company ? `${company} on ` : "the drive on "}${driveDate}` : `until ${end}`}
          </span>
        </p>
        <p className={cn("text-sm tabular-nums", behind ? "font-medium text-warning" : "text-muted")}>
          {behind ? "Behind schedule · " : ""}
          {done} of {total} tasks done
        </p>
      </div>
      <div className="mt-3 grid grid-cols-[4.5rem_1fr_2.75rem] items-center gap-x-3 gap-y-1.5 text-xs">
        <span className="text-muted">Time used</span>
        <div
          role="meter"
          aria-label="Time used before the drive"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={timePct}
          className="h-2 overflow-hidden rounded-full bg-border"
        >
          <div className="h-full origin-left animate-meter rounded-full bg-muted" style={{ width: `${timePct}%` }} />
        </div>
        <span className="text-right tabular-nums">{timePct}%</span>
        <span className="text-muted">Work done</span>
        <div
          role="meter"
          aria-label="Plan tasks done"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={workPct}
          className="h-2 overflow-hidden rounded-full bg-series-track"
        >
          <div className="h-full origin-left animate-meter rounded-full bg-series-1" style={{ width: `${workPct}%` }} />
        </div>
        <span className="text-right tabular-nums">{workPct}%</span>
      </div>
    </div>
  );
}
