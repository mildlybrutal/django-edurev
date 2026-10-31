"use client";

import { LogOut, Menu, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { NavItem } from "@/lib/nav";
import { ThemeSwitch } from "./theme-switch";

/** The booklet mark: three module spines. Authored SVG, flat colour. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" aria-hidden="true" className={className}>
      <rect width="28" height="28" rx="6" fill="#ffffff" />
      <rect x="6" y="6.5" width="16" height="4" rx="1" fill="#1e3fae" />
      <rect x="6" y="12" width="12" height="4" rx="1" fill="#0e7c86" />
      <rect x="6" y="17.5" width="9" height="4" rx="1" fill="#e8a317" />
    </svg>
  );
}

function NavList({
  items,
  home,
  pathname,
  onNavigate,
}: {
  items: NavItem[];
  home: string;
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <ul className="flex flex-col gap-0.5">
      {items.map(({ href, label, icon: Icon }) => {
        const active = href === home ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-150 ease-out",
                active
                  ? "bg-rail-active font-medium text-rail-active-foreground"
                  : "text-rail-muted hover:bg-rail-hover hover:text-rail-foreground",
              )}
            >
              <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={active ? 2.25 : 1.75} />
              <span className="truncate">{label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Chrome shared by every portal: committed cobalt rail, sticky header with theme switch and
 * notifications, mobile drawer. Visual only; every API call is authorized by Django.
 */
export function AppFrame({
  title,
  home,
  items,
  email,
  accountHref,
  headerExtras,
  onSignOut,
  signingOut,
  children,
}: {
  title: string;
  home: string;
  items: NavItem[];
  email: string;
  accountHref?: string;
  headerExtras?: ReactNode;
  onSignOut: () => void;
  signingOut: boolean;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const drawer = useRef<HTMLDialogElement>(null);
  const closeDrawer = () => drawer.current?.close();

  useEffect(() => {
    drawer.current?.close();
  }, [pathname]);

  const brand = (
    <Link href={home} className="flex items-center gap-3 rounded-md">
      <BrandMark className="size-8 shrink-0" />
      <span className="leading-tight">
        <span className="block text-sm font-semibold text-rail-foreground">Placement Readiness</span>
        <span className="block text-xs text-rail-muted">{title}</span>
      </span>
    </Link>
  );

  const account = (
    <div className="border-t border-white/15 px-3 pt-3 pb-4">
      {accountHref ? (
        <Link
          href={accountHref}
          aria-current={pathname === accountHref ? "page" : undefined}
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-rail-muted transition-colors hover:bg-rail-hover hover:text-rail-foreground"
        >
          <UserRound aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.75} />
          <span className="truncate">{email}</span>
        </Link>
      ) : (
        <p className="truncate px-3 py-2 text-sm text-rail-muted">{email}</p>
      )}
      <button
        type="button"
        onClick={onSignOut}
        disabled={signingOut}
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-rail-muted transition-colors hover:bg-rail-hover hover:text-rail-foreground disabled:opacity-60"
      >
        <LogOut aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.75} />
        Sign out
      </button>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* Outer column carries the rail colour the full page height; the inner rail stays in view. */}
      <div className="hidden w-64 shrink-0 bg-rail lg:block">
        <aside className="sticky top-0 flex h-screen flex-col">
          <div className="px-5 pt-5 pb-6">{brand}</div>
          <nav aria-label={`${title} navigation`} className="flex-1 overflow-y-auto px-3">
            <NavList items={items} home={home} pathname={pathname} />
          </nav>
          {account}
        </aside>
      </div>

      <dialog
        ref={drawer}
        aria-label="Menu"
        className="m-0 h-full max-h-none w-72 max-w-[85vw] animate-drawer-in bg-rail p-0 lg:hidden"
        onClick={(e) => {
          if (e.target === e.currentTarget) closeDrawer();
        }}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between px-5 pt-5 pb-6">
            {brand}
            <button
              type="button"
              onClick={closeDrawer}
              aria-label="Close menu"
              className="rounded-md p-1.5 text-rail-muted hover:bg-rail-hover hover:text-rail-foreground"
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </div>
          <nav aria-label={`${title} navigation`} className="flex-1 overflow-y-auto px-3">
            <NavList items={items} home={home} pathname={pathname} onNavigate={closeDrawer} />
          </nav>
          {account}
        </div>
      </dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-surface px-4 sm:px-6">
          <button
            type="button"
            onClick={() => drawer.current?.showModal()}
            aria-label="Open menu"
            className="-ml-1 rounded-md p-1.5 text-muted hover:bg-surface-muted hover:text-foreground lg:hidden"
          >
            <Menu aria-hidden="true" className="size-5" />
          </button>
          <Link href={home} className="flex items-center gap-2 lg:hidden">
            <span className="text-sm font-semibold">Placement Readiness</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <ThemeSwitch />
            {headerExtras}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

export function CenteredMessage({ children }: { children: ReactNode }) {
  return <div className="flex min-h-screen items-center justify-center text-sm text-muted">{children}</div>;
}
