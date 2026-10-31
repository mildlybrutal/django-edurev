"use client";

import { ChevronLeft, ChevronRight, Flag } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

export type CalendarItem = { id: number; date: string; title: string; done: boolean; checkpoint: boolean };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Month view of plan items by due date (P06 §8: preparation plan as a calendar). */
export function PlanCalendar({ items, initialMonth }: { items: CalendarItem[]; initialMonth?: string }) {
  const start = initialMonth ? new Date(`${initialMonth}T00:00:00`) : new Date();
  const [cursor, setCursor] = useState(new Date(start.getFullYear(), start.getMonth(), 1));
  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const item of items) map.set(item.date, [...(map.get(item.date) ?? []), item]);
    return map;
  }, [items]);

  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array.from({ length: offset }, () => null),
    ...Array.from({ length: days }, (_, i) => new Date(cursor.getFullYear(), cursor.getMonth(), i + 1)),
  ];
  const today = iso(new Date());

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
        >
          <ChevronLeft aria-hidden="true" className="size-4" />
          Previous
        </Button>
        <h3 className="text-sm font-semibold">
          {cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
        >
          Next
          <ChevronRight aria-hidden="true" className="size-4" />
        </Button>
      </div>
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Plan calendar">
        <div className="grid min-w-[640px] grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border">
          {WEEKDAYS.map((d) => (
            <div key={d} className="bg-surface-muted px-2 py-1 text-xs font-medium text-muted">
              {d}
            </div>
          ))}
          {cells.map((date, i) => {
            const key = date ? iso(date) : `blank-${i}`;
            const list = date ? (byDay.get(iso(date)) ?? []) : [];
            return (
              <div key={key} className={cn("min-h-24 bg-surface p-1.5", !date && "bg-surface-muted")}>
                {date && (
                  <>
                    <div
                      className={cn("mb-1 text-xs", iso(date) === today ? "font-semibold text-primary" : "text-muted")}
                    >
                      {date.getDate()}
                    </div>
                    <ul className="flex flex-col gap-1">
                      {list.map((item) => (
                        <li
                          key={item.id}
                          title={item.title}
                          className={cn(
                            "truncate rounded px-1.5 py-0.5 text-[11px] transition-colors",
                            item.done
                              ? "bg-success-soft text-success line-through"
                              : item.checkpoint
                                ? "bg-primary-soft font-medium text-primary"
                                : "bg-surface-muted",
                          )}
                        >
                          {item.checkpoint && <Flag aria-hidden="true" className="mr-1 inline size-3 align-[-1px]" />}
                          {item.title}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted">
        <Flag aria-hidden="true" className="size-3" />
        marks a checkpoint. Items show on their due date.
      </p>
    </div>
  );
}
