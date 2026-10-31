"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { OnboardingDialog } from "@/components/domain/onboarding-dialog";
import { canUsePortal, homeFor, portalFor, type Portal } from "@/lib/auth/roles";
import { useLogout, useMe } from "@/lib/auth/session";
import { NAV } from "@/lib/nav";
import { AppFrame, CenteredMessage } from "./app-frame";
import { NotificationBell } from "./notification-bell";

const ACCOUNT_PATH = "/account";

/**
 * Layout for an internal portal. Redirects away when the user is signed out, belongs to
 * another portal, or must finish two-factor set-up first. This is a convenience only: every
 * API call is authorized by Django.
 */
export function PortalShell({ portal, children }: { portal: Portal | "any"; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me, isPending, isError } = useMe();
  const logout = useLogout();

  const resolved: Portal | null = me ? (portal === "any" ? portalFor(me.roles) : portal) : null;
  const allowed = !!me && !!resolved && canUsePortal(me.roles, resolved);
  const needsMfa = !!me?.mfa?.setup_required && pathname !== ACCOUNT_PATH;

  useEffect(() => {
    if (isPending || isError) return;
    if (!me) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!allowed) router.replace(homeFor(me.roles));
    else if (needsMfa) router.replace(ACCOUNT_PATH);
  }, [isPending, isError, me, allowed, needsMfa, pathname, router]);

  if (isError) {
    return <CenteredMessage>Could not reach the server. Refresh to try again.</CenteredMessage>;
  }
  if (!allowed || !resolved || needsMfa) {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }

  const nav = NAV[resolved];
  const items = nav.items.filter((item) => !item.roles || item.roles.some((r) => me.roles.includes(r)));

  return (
    <AppFrame
      title={nav.title}
      home={`/${resolved}`}
      items={items}
      email={me.email}
      accountHref={ACCOUNT_PATH}
      headerExtras={<NotificationBell />}
      onSignOut={() => logout.mutate(undefined, { onSettled: () => router.replace("/login") })}
      signingOut={logout.isPending}
    >
      {children}
      {resolved === "student" && <OnboardingDialog />}
    </AppFrame>
  );
}
