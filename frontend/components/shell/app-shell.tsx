"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { usePathname } from "next/navigation";
import { NAV, NAV_GROUPS, isActive } from "@/lib/nav";
import { cn } from "@/lib/cn";
import { Tooltip } from "@/components/ui/tooltip";
import { NavIcon } from "./nav-icon";
import { SystemStatus } from "./system-status";
import { UserSwitcher } from "./user-switcher";
import { Wordmark } from "./wordmark";

function usePendingApprovals(pathname: string) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () => apiGet<{ pending: number }>("/approvals/count").then((r) => alive && setCount(r.pending)).catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [pathname]); // refresh on navigation too, e.g. right after approving
  return count;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const pendingApprovals = usePendingApprovals(pathname);
  const current = NAV.find((n) => isActive(pathname, n.href));

  return (
    <div className="min-h-[100dvh] md:grid md:grid-cols-[220px_1fr]">
      {/* Desktop sidebar: sits on the canvas, no border */}
      <aside className="sticky top-0 z-[var(--z-nav)] hidden h-[100dvh] flex-col justify-between px-3 py-4 md:flex">
        <div className="flex flex-col gap-5">
          <div className="px-2 pt-0.5">
            <Wordmark />
          </div>
          <nav aria-label="Main" className="flex flex-col gap-4">
            {NAV_GROUPS.map((group, gi) => (
              <div key={gi} className="flex flex-col gap-px">
                {group.label && <p className="px-2 pb-1 text-xs font-medium text-subtle">{group.label}</p>}
                {group.items.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Tooltip key={item.href} label={item.hint} side="right" className="flex">
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex h-8 w-full items-center gap-2.5 rounded-control px-2 text-[13px] font-medium",
                        active ? "bg-surface-2 text-fg" : "text-muted hover:bg-surface hover:text-fg",
                      )}
                    >
                      <span className={active ? "text-accent-ink" : "text-subtle"}>
                        <NavIcon name={item.icon} active={active} />
                      </span>
                      {item.label}
                      {item.href === "/approvals" && pendingApprovals > 0 && (
                        <span className="tabular ml-auto grid h-5 min-w-5 place-items-center rounded-full bg-negative px-1.5 text-[11px] font-semibold text-white">
                          {pendingApprovals}
                        </span>
                      )}
                    </Link>
                    </Tooltip>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>
        <div className="flex flex-col gap-4">
          <UserSwitcher />
          <div className="px-2">
            <SystemStatus />
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-[var(--z-nav)] flex h-12 items-center justify-between border-b border-line bg-bg/90 px-4 backdrop-blur md:hidden">
        <Wordmark />
        <UserSwitcher compact />
      </div>

      {/* Inset content panel */}
      <div className="md:py-2 md:pr-2">
        <main className="min-h-[calc(100dvh-1rem)] pb-24 md:rounded-panel md:border md:border-line md:bg-panel md:pb-0">
          <header className="hidden h-12 items-center border-b border-line px-6 md:flex">
            <h1 className="text-[13px] font-medium text-fg">{current?.label}</h1>
          </header>
          <div key={pathname} className="page-enter mx-auto flex w-full max-w-[1080px] flex-col gap-8 px-4 py-6 md:px-8 md:py-8">
            {children}
          </div>
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-[var(--z-nav)] grid grid-cols-7 border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn("flex h-14 flex-col items-center justify-center gap-1 text-[10px] font-medium", active ? "text-fg" : "text-subtle")}
            >
              <span className={active ? "text-accent-ink" : undefined}>
                <NavIcon name={item.icon} active={active} size={18} />
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
