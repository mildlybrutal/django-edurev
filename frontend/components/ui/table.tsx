import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function Table({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    // Focusable so keyboard users can scroll wide tables (WCAG 2.1.1).
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={caption ?? "Table"}>
      <table className="w-full text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-border bg-surface-muted/60 px-4 py-2 text-left text-xs font-medium text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b border-border px-4 py-2.5 align-top", className)} {...props} />;
}
