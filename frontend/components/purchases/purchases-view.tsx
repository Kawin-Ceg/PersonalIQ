"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CaretRight, CheckCircle, ClockCountdown, Receipt, Star } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Tooltip } from "@/components/ui/tooltip";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { OrderSummary } from "@/types/receipt";
import { ReceiptStateBadge } from "./receipt-state";

export function shortDate(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
}

export function PurchasesView() {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    apiGet<OrderSummary[]>("/orders").then(setOrders).catch(() => setFailed(true));
  }, []);

  const paid = orders?.filter((o) => o.state === "paid") ?? [];
  const other = orders?.filter((o) => o.state !== "paid") ?? [];

  return (
    <div className="flex max-w-[860px] flex-col gap-8">
      <PageHeader
        icon={<Receipt size={18} />}
        title="Purchases"
        description="Orders PayPal has confirmed, each with a decision receipt: what you asked for, how it was chosen, and what to follow up on."
      />
      {failed ? (
        <p className="text-[13px] text-negative">Couldn&apos;t load purchases. Check that the API is running.</p>
      ) : orders === null ? (
        <div className="skeleton h-24 w-full" aria-busy="true" aria-label="Loading" />
      ) : orders.length === 0 ? (
        <EmptyState
          icon={<Receipt size={20} />}
          title="No purchases yet"
          body="A purchase appears here once you approve an order. It's marked paid only after PayPal confirms the payment."
          action={
            <Link href="/" className="text-[13px] font-medium text-fg underline underline-offset-4">
              Ask for something on Home
            </Link>
          }
        />
      ) : (
        <>
          <Section title={`Paid (${paid.length})`} description="Confirmed by PayPal. Open one for its decision receipt." icon={<CheckCircle size={14} />}>
            {paid.length ? <OrderList orders={paid} /> : <p className="text-[13px] text-muted">Nothing paid yet.</p>}
          </Section>
          {other.length > 0 && (
            <Section title={`Other orders (${other.length})`} description="Approved but not paid, waiting on PayPal, or not bought." icon={<ClockCountdown size={14} />}>
              <OrderList orders={other} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}

function OrderList({ orders }: { orders: OrderSummary[] }) {
  return (
    <ul className="overflow-hidden rounded-card border border-line">
      {orders.map((o) => (
        <li key={o.order_id} className="border-b border-line last:border-b-0">
          <Link href={`/purchases/${o.order_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface">
            <span className="grid size-8 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">
              <Receipt size={16} aria-hidden />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-[13px] font-medium text-fg">{o.objective || "Order"}</span>
              <span className="truncate text-xs text-subtle">
                {o.items} items
                {o.paid_at ? ` · paid ${shortDate(o.paid_at)}` : o.updated_at ? ` · updated ${shortDate(o.updated_at)}` : ""}
                {o.charged && o.charged.currency !== o.currency ? ` · charged ${formatMoney(o.charged.amount, o.charged.currency)} ${o.charged.currency}` : ""}
              </span>
            </span>
            {o.feedback_left > 0 && (
              <Tooltip label="Items you haven't rated yet. Ratings change future picks.">
                <span tabIndex={0} className="inline-flex h-6 shrink-0 cursor-help items-center gap-1 rounded-full border border-line px-2 text-xs text-muted">
                  <Star size={12} aria-hidden /> {o.feedback_left} to rate
                </span>
              </Tooltip>
            )}
            <ReceiptStateBadge state={o.state} />
            <span className="tabular w-28 shrink-0 text-right text-[13px] font-medium text-fg">{formatMoney(o.total, o.currency)}</span>
            <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}
