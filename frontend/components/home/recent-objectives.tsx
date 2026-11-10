"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CaretRight, Sparkle } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { WorkflowSummary } from "@/types/api";

const SHOWN = 5;

export function RecentObjectives() {
  const [items, setItems] = useState<WorkflowSummary[] | null>(null);

  useEffect(() => {
    apiGet<WorkflowSummary[]>("/workflows").then(setItems).catch(() => setItems([]));
  }, []);

  if (items === null) return <div className="skeleton h-24 w-full" aria-busy="true" aria-label="Loading" />;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<Sparkle size={20} />}
        title="No objectives yet"
        body="When you make a request above, it becomes an objective here with its plan, budget and progress."
      />
    );
  }
  return (
    <ul className="overflow-hidden rounded-card border border-line">
      {items.slice(0, SHOWN).map((w) => (
        <li key={w.id} className="border-b border-line last:border-b-0">
          <Link href={w.objective_id ? `/objectives/${w.objective_id}` : `/activity?w=${w.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-[13px] font-medium text-fg">{w.objective}</span>
              <span className="truncate text-xs text-subtle">
                {new Date(w.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                {w.total && w.currency && ` · ${formatMoney(w.total, w.currency)}`}
              </span>
            </span>
            <StatusPill status={w.status} />
            <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}
