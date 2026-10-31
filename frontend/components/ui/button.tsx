import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "next";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary-hover",
  secondary: "border border-border bg-surface text-foreground hover:border-border-strong hover:bg-surface-muted",
  ghost: "text-foreground hover:bg-surface-muted",
  danger: "bg-danger text-danger-foreground hover:opacity-90",
  next: "bg-next text-next-foreground hover:opacity-90",
};

const sizes: Record<Size, string> = { sm: "h-8 px-3", md: "h-9 px-4" };

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium whitespace-nowrap select-none",
        "transition-[background-color,border-color,color,opacity,transform] duration-150 ease-out active:scale-[0.97]",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100",
        sizes[size],
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
