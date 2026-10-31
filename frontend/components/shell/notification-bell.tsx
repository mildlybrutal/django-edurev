"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui/toast";
import { api, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";

export function NotificationBell() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => unwrap(await api.GET("/api/v1/notifications/unread/")).unread,
    refetchInterval: 60_000,
  });
  const list = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: async () => unwrap(await api.GET("/api/v1/notifications/")).results,
    enabled: open,
  });
  const markRead = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/notifications/mark-read/", { body: {} })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  // Toast when the unread count rises after the first load (a new notification arrived).
  const push = useToast();
  const seen = useRef<number | null>(null);
  useEffect(() => {
    if (unread.data === undefined) return;
    if (seen.current !== null && unread.data > seen.current) {
      const fresh = unread.data - seen.current;
      push({ tone: "info", title: fresh === 1 ? "You have a new notification" : `${fresh} new notifications` });
    }
    seen.current = unread.data;
  }, [unread.data, push]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !panel.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const count = unread.data ?? 0;
  return (
    <div className="relative" ref={panel}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
        onClick={() => setOpen((o) => !o)}
        className="relative inline-flex size-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
      >
        <Bell aria-hidden="true" className="size-[18px]" strokeWidth={1.75} />
        {count > 0 && (
          <span className="absolute top-1 right-1 min-w-4 animate-pop-in rounded-full bg-primary px-1 text-center text-[11px] leading-4 font-semibold text-primary-foreground tabular-nums">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] origin-top-right animate-pop-in rounded-lg border border-border bg-surface-raised shadow-pop">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <span className="text-sm font-semibold">Notifications</span>
            <button
              type="button"
              className="text-xs text-primary disabled:text-muted"
              disabled={count === 0 || markRead.isPending}
              onClick={() => markRead.mutate()}
            >
              Mark all read
            </button>
          </div>
          <ul className="max-h-96 divide-y divide-border overflow-y-auto">
            {list.isPending && <li className="px-4 py-3 text-sm text-muted">Loading…</li>}
            {list.data?.length === 0 && <li className="px-4 py-3 text-sm text-muted">Nothing yet.</li>}
            {list.data?.map((n) => (
              <li key={n.id} className={cn("px-4 py-2.5 text-sm", !n.read_at && "bg-primary-soft")}>
                {n.link ? (
                  <Link href={n.link} onClick={() => setOpen(false)} className="font-medium hover:underline">
                    {n.title}
                  </Link>
                ) : (
                  <span className="font-medium">{n.title}</span>
                )}
                {n.body && <p className="mt-0.5 text-muted">{n.body}</p>}
                <p className="mt-0.5 text-xs text-muted">{new Date(n.created_at).toLocaleString()}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
