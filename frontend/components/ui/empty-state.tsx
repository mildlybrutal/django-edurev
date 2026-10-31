import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

/** Shown where real data does not exist yet. Never substitute invented numbers. */
export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-border-strong px-6 py-10 text-center">
      <span aria-hidden="true" className="mb-3 text-muted">
        {icon ?? <Inbox className="size-6" strokeWidth={1.5} />}
      </span>
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="mt-1 max-w-prose text-sm text-muted">{children}</div>}
    </div>
  );
}
