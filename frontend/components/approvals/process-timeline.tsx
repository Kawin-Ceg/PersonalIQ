"use client";

import { CheckCircle, Gear, Robot, SealCheck, User, WarningCircle, ChatCircleText } from "@phosphor-icons/react";
import { cn } from "@/lib/cn";
import type { TimelineEvent } from "@/types/api";

const ICON: Record<TimelineEvent["kind"], { icon: React.ReactNode; cls: string }> = {
  start: { icon: <ChatCircleText size={14} />, cls: "text-fg" },
  agent: { icon: <Robot size={14} />, cls: "text-muted" },
  decision: { icon: <SealCheck size={14} />, cls: "text-caution" },
  user: { icon: <User size={14} />, cls: "text-fg" },
  system: { icon: <Gear size={14} />, cls: "text-muted" },
  success: { icon: <CheckCircle size={14} weight="fill" />, cls: "text-positive" },
  danger: { icon: <WarningCircle size={14} weight="fill" />, cls: "text-negative" },
};

/** Everything that happened to this order, oldest first: request, agents, approvals, your changes. */
export function ProcessTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="flex flex-col">
      {events.map((e, i) => (
        <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
          {i < events.length - 1 && <span className="absolute bottom-0 left-[13px] top-7 w-px bg-line" aria-hidden />}
          <span className={cn("z-[1] grid size-7 shrink-0 place-items-center rounded-full border border-line bg-panel", ICON[e.kind].cls)}>{ICON[e.kind].icon}</span>
          <div className="flex min-w-0 flex-col gap-0.5 pt-0.5">
            <p className="flex flex-wrap items-baseline gap-x-2 text-[13px] font-medium text-fg">
              {e.title}
              <span className="tabular text-xs font-normal text-subtle">{new Date(e.at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" })}</span>
            </p>
            {e.detail && <p className="text-[13px] leading-relaxed text-muted">{e.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
