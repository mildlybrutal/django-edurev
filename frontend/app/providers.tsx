"use client";

import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { toast, ToastProvider } from "@/components/ui/toast";

/**
 * A mutation opts into a success toast with `meta: { toast: "Saved" }` (or a function of its
 * variables). Errors stay inline next to the control that failed, where the user is looking.
 */
declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: { toast?: string | ((variables: never, data: never) => string); toastBody?: string };
  }
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
        mutationCache: new MutationCache({
          onSuccess: (data, variables, _context, mutation) => {
            const message = mutation.meta?.toast;
            if (!message) return;
            const title =
              typeof message === "function"
                ? (message as (v: unknown, d: unknown) => string)(variables, data)
                : message;
            toast({ tone: "success", title, body: mutation.meta?.toastBody });
          },
        }),
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
