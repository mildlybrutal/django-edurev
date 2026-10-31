"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/cn";
import { applyTheme, useTheme, type ThemeChoice } from "@/lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon },
];

/** Segmented Light / System / Dark control. Radio semantics, arrow keys move the choice. */
export function ThemeSwitch({ className }: { className?: string }) {
  const theme = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className={cn("inline-flex rounded-lg border border-border bg-surface-muted p-0.5", className)}
      onKeyDown={(e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        const i = OPTIONS.findIndex((o) => o.value === theme);
        const next = OPTIONS[(i + (e.key === "ArrowRight" ? 1 : OPTIONS.length - 1)) % OPTIONS.length];
        applyTheme(next.value);
        (e.currentTarget.querySelector(`[data-value="${next.value}"]`) as HTMLElement | null)?.focus();
      }}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            data-value={value}
            tabIndex={active ? 0 : -1}
            onClick={() => applyTheme(value)}
            className={cn(
              "inline-flex h-7 w-8 items-center justify-center rounded-md text-muted transition-[background-color,color,box-shadow] duration-150 ease-out",
              active ? "bg-surface text-foreground shadow-sm" : "hover:text-foreground",
            )}
          >
            <Icon aria-hidden="true" className="size-4" strokeWidth={1.75} />
          </button>
        );
      })}
    </div>
  );
}
