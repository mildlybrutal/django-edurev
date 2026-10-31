"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { homeFor } from "@/lib/auth/roles";
import { useMe } from "@/lib/auth/session";

export default function Home() {
  const router = useRouter();
  const { data: me, isPending } = useMe();

  useEffect(() => {
    if (!isPending) router.replace(me ? homeFor(me.roles) : "/login");
  }, [isPending, me, router]);

  return <div className="flex min-h-screen items-center justify-center text-sm text-muted">Loading…</div>;
}
