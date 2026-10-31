import { useId, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function TextField({
  label,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className="h-9 rounded-md border border-border bg-surface px-3 text-sm transition-[border-color] duration-150 placeholder:text-muted hover:border-border-strong focus:border-primary disabled:bg-surface-muted disabled:text-muted aria-invalid:border-danger"
        {...props}
      />
      {error && (
        <p id={errorId} className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
