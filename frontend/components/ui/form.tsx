import { useId, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const control =
  "rounded-md border border-border bg-surface px-3 text-sm transition-[border-color] duration-150 placeholder:text-muted hover:border-border-strong focus:border-primary disabled:bg-surface-muted disabled:text-muted";

export function SelectField({
  label,
  children,
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <select id={id} className={cn(control, "h-9 px-2")} {...props}>
        {children}
      </select>
    </div>
  );
}

export function TextAreaField({
  label,
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <textarea id={id} className={cn(control, "min-h-24 py-2")} {...props} />
    </div>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="animate-fade-in rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}

export function FormSuccess({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="status" className="rounded-md bg-success-soft px-3 py-2 text-sm text-success">
      {message}
    </p>
  );
}
