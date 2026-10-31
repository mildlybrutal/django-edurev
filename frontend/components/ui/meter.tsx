import { cn } from "@/lib/cn";

/** Horizontal meter. Fills from the left on mount (off under reduced motion). */
export function Meter({
  value,
  label,
  className,
  barClassName,
}: {
  value: number;
  label: string;
  className?: string;
  barClassName?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-series-track", className)}
    >
      <div
        className={cn("h-full origin-left animate-meter rounded-full bg-series-1", barClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
