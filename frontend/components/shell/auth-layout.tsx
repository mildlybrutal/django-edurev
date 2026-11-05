import type { ReactNode } from "react";
import { BrandMark } from "./app-frame";
import { ThemeSwitch } from "./theme-switch";

const STEPS = [
  {
    n: "01",
    // White and navy spines; an orange module hue would vanish on the orange panel.
    hue: "bg-rail-active",
    title: "Evidence",
    body: "Projects, assessments, GitHub and LeetCode, verified by faculty.",
  },
  {
    n: "02",
    hue: "bg-mod-teal",
    title: "Readiness",
    body: "Eligibility and role readiness, scored separately and explained.",
  },
  {
    n: "03",
    hue: "bg-mod-cobalt",
    title: "Plan",
    body: "Ranked gaps turned into dated checkpoints before each drive.",
  },
];

/** Sign-in and sign-up frame: committed orange panel with the product story, form on the right. */
export function AuthLayout({
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-[26rem] shrink-0 flex-col justify-between bg-rail px-10 py-10 text-rail-foreground lg:flex">
        <div className="flex items-center gap-3">
          <BrandMark className="size-9" />
          <span className="text-base font-semibold">Placement Readiness</span>
        </div>
        <div>
          <p className="mb-6 text-2xl leading-snug font-semibold tracking-tight text-balance">
            Am I ready for this role, and what do I do next?
          </p>
          <ol className="flex flex-col gap-3">
            {STEPS.map((s) => (
              <li key={s.n} className="flex overflow-hidden rounded-lg bg-white/10">
                <span
                  aria-hidden="true"
                  className={`flex w-11 shrink-0 items-center justify-center text-sm font-semibold tabular-nums ${s.hue} ${s.hue === "bg-mod-marigold" ? "text-mod-ink-dark" : s.hue === "bg-rail-active" ? "text-rail-active-foreground" : "text-mod-ink-light"}`}
                >
                  {s.n}
                </span>
                <span className="px-4 py-3 text-sm">
                  <span className="block font-semibold">{s.title}</span>
                  <span className="text-rail-muted">{s.body}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-xs text-rail-muted">An institutional placement-readiness platform.</p>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex justify-end px-4 py-4 sm:px-6">
          <ThemeSwitch />
        </div>
        <div className="flex flex-1 items-start justify-center px-4 pb-12 sm:items-center">
          <div className={wide ? "w-full max-w-xl" : "w-full max-w-sm"}>
            <div className="mb-6 flex items-center gap-3 lg:hidden">
              <BrandMark className="size-8" />
              <span className="font-semibold">Placement Readiness</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 mb-6 text-sm text-muted">{description}</p>
            <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">{children}</div>
            {footer && <div className="mt-5 text-center text-sm text-muted">{footer}</div>}
          </div>
        </div>
      </main>
    </div>
  );
}
