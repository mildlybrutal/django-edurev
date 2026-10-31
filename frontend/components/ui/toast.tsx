"use client";

import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ToastTone = "success" | "error" | "info";
type Toast = { id: number; tone: ToastTone; title: string; body?: string };
type Push = (toast: Omit<Toast, "id">) => void;

const ToastContext = createContext<Push>(() => {});
const DURATION = 4500;

/** Imperative bridge for code outside React (the TanStack mutation cache). */
let externalPush: Push | null = null;
export function toast(t: Omit<Toast, "id">) {
  externalPush?.(t);
}

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const push = useCallback<Push>((t) => {
    const id = next.current++;
    setToasts((list) => [...list.slice(-3), { ...t, id }]);
  }, []);
  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  useEffect(() => {
    externalPush = push;
    return () => {
      externalPush = null;
    };
  }, [push]);

  const value = useMemo(() => push, [push]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Polite for success/info; errors also announce but never steal focus. */}
      <div
        aria-live="polite"
        aria-relevant="additions"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:bottom-5"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const TONES: Record<ToastTone, { Icon: typeof Info; icon: string }> = {
  success: { Icon: CircleCheck, icon: "text-success" },
  error: { Icon: CircleAlert, icon: "text-danger" },
  info: { Icon: Info, icon: "text-primary" },
};

function ToastItem({ toast: t, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused) return;
    const timer = setTimeout(onDismiss, DURATION);
    return () => clearTimeout(timer);
  }, [paused, onDismiss]);
  const { Icon, icon } = TONES[t.tone];
  return (
    <div
      role={t.tone === "error" ? "alert" : "status"}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      className="pointer-events-auto flex w-full max-w-sm animate-toast-in items-start gap-3 rounded-lg border border-border bg-surface-raised px-4 py-3 text-sm shadow-pop sm:w-96"
    >
      <Icon aria-hidden="true" className={cn("mt-0.5 size-4 shrink-0", icon)} strokeWidth={2} />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t.title}</p>
        {t.body && <p className="mt-0.5 text-muted">{t.body}</p>}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="-m-1 rounded p-1 text-muted transition-colors hover:text-foreground"
      >
        <X aria-hidden="true" className="size-4" />
      </button>
    </div>
  );
}
