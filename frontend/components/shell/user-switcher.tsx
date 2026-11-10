"use client";

import { useEffect, useState } from "react";
import { CaretUpDown } from "@phosphor-icons/react";
import { apiGet, getCurrentUserId, setCurrentUserId } from "@/lib/api";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import type { DemoUser } from "@/types/api";

/** Switch between demo profiles. A native select keeps it keyboard and screen-reader friendly. */
export function UserSwitcher({ compact = false }: { compact?: boolean }) {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [current, setCurrent] = useState<string | null>(null);

  useEffect(() => {
    apiGet<DemoUser[]>("/users")
      .then((list) => {
        setUsers(list);
        const saved = getCurrentUserId();
        setCurrent(list.some((u) => u.id === saved) ? saved : (list[0]?.id ?? null));
      })
      .catch(() => setUsers([]));
  }, []);

  if (users.length === 0 || !current) return null;
  const me = users.find((u) => u.id === current)!;
  const initials = me.name.split(" ").map((p) => p[0]).join("").slice(0, 2);

  return (
    <Tooltip label={`Demo profile, shown in ${me.currency}. Switch to see PersonalIQ personalise for someone else.`} side={compact ? "bottom" : "right"} className="flex">
    <label
      className={cn(
        "relative flex items-center gap-2.5 rounded-control hover:bg-surface",
        compact ? "h-8 px-1.5" : "h-10 w-full px-2",
      )}
    >
      <span className="sr-only">Demo profile</span>
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[10px] font-semibold text-fg">{initials}</span>
      {!compact && (
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[13px] font-medium text-fg">{me.name}</span>
          <span className="text-[11px] text-subtle">Demo profile · {me.currency}</span>
        </span>
      )}
      <CaretUpDown size={12} className="ml-auto text-subtle" aria-hidden />
      <select
        value={current}
        onChange={(e) => {
          setCurrentUserId(e.target.value);
          window.location.reload(); // every screen reloads for the new profile
        }}
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name} ({u.currency})
          </option>
        ))}
      </select>
    </label>
    </Tooltip>
  );
}
