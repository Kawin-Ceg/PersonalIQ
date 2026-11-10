"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CaretRight, ClockCountdown, SealCheck, WarningOctagon } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { ApprovalSummary } from "@/types/api";

export function ApprovalList() {
  const [items, setItems] = useState<ApprovalSummary[] | null>(null);
  useEffect(() => {
    apiGet<ApprovalSummary[]>("/approvals").then(setItems).catch(() => setItems([]));
  }, []);

  return (
    <div className="flex max-w-[860px] flex-col gap-8">
      <PageHeader
        icon={<SealCheck size={18} />}
        title="Approvals"
        description="Every purchase waits here for your yes. You approve one exact order, and if anything changes it asks again."
      />
      <Section title="Waiting for you" description="Open one to review the items, decide on the risky ones, and approve." icon={<ClockCountdown size={14} />}>
        {items === null ? (
          <div className="skeleton h-24 w-full" aria-busy="true" aria-label="Loading" />
        ) : items.length === 0 ? (
          <EmptyState icon={<SealCheck size={20} />} title="Nothing waiting for you" body="When PersonalIQ proposes an order, it appears here with the items, total, budget impact and the reason for each pick." />
        ) : (
          <ul className="overflow-hidden rounded-card border border-line">
            {items.map((a) => (
              <li key={a.id} className="border-b border-line last:border-b-0">
                <Link href={`/approvals/${a.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface">
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-[13px] font-medium text-fg">{a.objective}</span>
                    <span className="flex flex-wrap items-center gap-x-2 text-xs text-subtle">
                      {a.items} items
                      {a.needs_decision_left > 0 ? (
                        <span className="inline-flex items-center gap-1 text-negative">
                          <WarningOctagon size={12} aria-hidden /> {a.needs_decision_left} need your decision
                        </span>
                      ) : (
                        <span className="text-positive">Ready to approve</span>
                      )}
                    </span>
                  </span>
                  <span className="tabular text-[14px] font-semibold text-fg">{formatMoney(a.total, a.currency)}</span>
                  <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
