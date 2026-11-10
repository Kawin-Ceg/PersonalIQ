"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  CaretDown,
  CaretRight,
  Check,
  CheckCircle,
  ClockCountdown,
  Eye,
  ListChecks,
  SealCheck,
  ShieldCheck,
  WarningCircle,
  WarningOctagon,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { CategoryIcon } from "@/components/ui/category-icon";
import { Dialog } from "@/components/ui/dialog";
import { Chip } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";
import type { ApprovalItem, ApprovalView, RiskLevel } from "@/types/api";
import { ItemDialog } from "./item-dialog";
import { PayPalCheckout } from "./paypal-checkout";
import { ProcessTimeline } from "./process-timeline";
import { RiskBadge } from "./risk-badge";

const REJECT_REASONS = [
  { value: "too_expensive", label: "Too expensive" },
  { value: "wrong_items", label: "Not the right items" },
  { value: "not_now", label: "Not now" },
  { value: "other", label: "Something else" },
];

function hoursLeft(iso: string) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "expired";
  const h = Math.floor(ms / 3_600_000);
  return h >= 1 ? `${h} h left` : `${Math.max(1, Math.round(ms / 60_000))} min left`;
}

function errorText(e: unknown) {
  if (e instanceof ApiError) {
    try {
      return (JSON.parse(e.message) as { message?: string }).message ?? e.message;
    } catch {
      return e.message;
    }
  }
  return "Something went wrong.";
}

export function ApprovalDetail({ id }: { id: string }) {
  const [a, setA] = useState<ApprovalView | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<ApprovalItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfident, setShowConfident] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGet<ApprovalView>(`/approvals/${id}`).then(setA).catch(() => setFailed(true));
  }, [id]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<ApprovalView>) {
    setBusy(true);
    setError(null);
    try {
      const next = await fn();
      setA(next);
      if (next.id !== id) window.history.replaceState(null, "", `/approvals/${next.id}`); // the order changed: new approval
      setSelected(null);
    } catch (e) {
      setError(errorText(e));
      load(); // show the real current state
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <p className="text-[13px] text-negative">Couldn&apos;t load this approval. Check that the API is running.</p>;
  if (!a) return <div className="skeleton h-64 w-full max-w-[860px]" aria-busy="true" aria-label="Loading" />;

  const cur = a.order.currency;
  const pending = a.status === "pending";
  const groups: { level: RiskLevel; title: string; description: string; icon: React.ReactNode }[] = [
    { level: "needs_decision", title: "Needs your decision", description: "Keep, swap or remove each of these before you can approve.", icon: <WarningOctagon size={14} className="text-negative" /> },
    { level: "review", title: "Worth a look", description: "Some risk, no action needed.", icon: <Eye size={14} className="text-caution" /> },
    { level: "auto", title: "PersonalIQ is confident", description: "Strong matches at sensible prices.", icon: <ShieldCheck size={14} className="text-positive" /> },
  ];
  const decidedCount = a.items.filter((i) => i.risk.level === "needs_decision" && i.decision).length;
  const mustCount = a.items.filter((i) => i.risk.level === "needs_decision").length;

  return (
    <div className="flex max-w-[860px] flex-col gap-8 pb-24">
      <PageHeader icon={<SealCheck size={18} />} title={a.objective || "Approve order"} description="Check the exact order, decide on the risky items, then approve. Nothing is paid until you do." />

      {/* Status banners */}
      {a.status === "approved" && (
        <Banner
          tone="positive"
          icon={<CheckCircle size={18} weight="fill" />}
          title="Approved"
          body={`You approved version ${a.order_version} for ${formatMoney(a.order.total, cur)}.${a.payment.order_status === "paid" ? "" : " Next: pay with PayPal Sandbox below."}`}
        />
      )}
      {a.status === "invalidated" && (
        <Banner
          tone="caution"
          icon={<WarningCircle size={18} weight="fill" />}
          title="This approval no longer applies"
          body="The order or a price changed after you approved it, so nothing can be paid with this approval."
          action={a.replaced_by ? <Link className="font-medium text-fg underline underline-offset-4" href={`/approvals/${a.replaced_by}`}>Review the updated order</Link> : undefined}
        />
      )}
      {a.status === "approved" && <PayPalCheckout a={a} onChange={load} />}
      {a.status === "rejected" && <Banner tone="neutral" icon={<X size={18} />} title="Rejected" body="Nothing was bought. PersonalIQ will remember why if you gave a reason." />}
      {a.status === "expired" && <Banner tone="negative" icon={<ClockCountdown size={18} />} title="This approval expired" body="Approvals last 24 hours. Start the request again from Home to get a fresh order." />}
      {a.status === "superseded" && (
        <Banner
          tone="caution"
          icon={<WarningCircle size={18} weight="fill" />}
          title="The order changed"
          body="This version is out of date, so it can't be approved."
          action={a.replaced_by ? <Link className="font-medium text-fg underline underline-offset-4" href={`/approvals/${a.replaced_by}`}>Open the current version</Link> : undefined}
        />
      )}

      {/* The approval card */}
      <section className="flex flex-col gap-4 rounded-card border border-line p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-subtle">Total to approve, shipping included</span>
            <span className="tabular text-3xl font-semibold tracking-tight text-fg">{formatMoney(a.order.total, cur)}</span>
            <span className={cn("text-[13px]", a.budget.within_budget === false ? "font-medium text-negative" : "text-muted")}>{a.budget.explanation}</span>
          </div>
          <div className="flex flex-col items-end gap-1 text-xs text-subtle">
            <span>
              Pay with <span className="font-medium text-fg">{a.payment_method}</span>
            </span>
            {pending && (
              <Tooltip label="Approvals expire so an old yes can't be used later.">
                <span tabIndex={0} className="inline-flex cursor-help items-center gap-1">
                  <ClockCountdown size={12} aria-hidden /> {hoursLeft(a.expires_at)}
                </span>
              </Tooltip>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-3">
          <Stat label="Items" value={String(a.items.length)} />
          <Stat label="Shipping" value={Number(a.order.shipping) === 0 ? "Free" : formatMoney(a.order.shipping, cur)} />
          {a.budget.used_pct !== undefined && <Stat label="Budget used" value={`${a.budget.used_pct}%`} />}
          {a.budget.remaining_after && <Stat label="Left" value={formatMoney(a.budget.remaining_after, cur)} />}
          <Tooltip label="Each change creates a new version. An approval only ever covers one exact version.">
            <span tabIndex={0} className="cursor-help">
              <Stat label="Version" value={String(a.order_version)} />
            </span>
          </Tooltip>
        </div>
        <p className="text-xs text-subtle">
          From {a.order.merchants.join(", ")}. No tax data in the demo catalog.
          {a.charge.currency !== cur && ` PayPal charges ${formatMoney(a.charge.total, a.charge.currency)} ${a.charge.currency} (${a.charge.rate_note}). Approving covers both amounts.`}
        </p>
      </section>

      {/* Items grouped by risk */}
      {groups.map((g) => {
        const items = a.items.filter((i) => i.risk.level === g.level);
        if (items.length === 0) return null;
        const collapsed = g.level === "auto" && !showConfident;
        return (
          <Section
            key={g.level}
            title={`${g.title} (${items.length})`}
            description={g.level === "needs_decision" && pending ? `${decidedCount} of ${mustCount} decided. ${g.description}` : g.description}
            icon={g.icon}
          >
            {collapsed ? (
              <button type="button" onClick={() => setShowConfident(true)} className="flex h-10 items-center gap-1.5 rounded-card border border-line px-4 text-[13px] font-medium text-muted hover:bg-surface hover:text-fg">
                <CaretDown size={12} aria-hidden /> Show {items.length} items
              </button>
            ) : (
              <ul className="overflow-hidden rounded-card border border-line">
                {items.map((i) => (
                  <li key={i.id} className="border-b border-line last:border-b-0">
                    <button onClick={() => setSelected(i)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface">
                      <span className="grid size-8 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">
                        <CategoryIcon category={i.product.category} />
                      </span>
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate text-[13px] font-medium text-fg">{i.product.name}</span>
                        <span className="truncate text-xs text-subtle">
                          {i.risk.factors[0]?.reason ?? `${needLabel(i.product.attributes.need ?? "general")} · ${i.product.merchant.name}`}
                        </span>
                      </span>
                      {i.decision ? (
                        <span className="inline-flex h-6 shrink-0 items-center gap-1 rounded-full border border-positive/40 px-2 text-xs font-semibold text-positive">
                          <Check size={12} aria-hidden /> {i.decision === "kept" ? "Kept" : "Swapped"}
                        </span>
                      ) : (
                        <RiskBadge level={i.risk.level} score={i.risk.score} />
                      )}
                      <span className="tabular w-28 shrink-0 text-right text-[13px] font-medium text-fg">{formatMoney(i.line_total, cur)}</span>
                      <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        );
      })}

      <Section title="Timeline" description="Everything that happened to this order, from your request to now." icon={<ListChecks size={14} />}>
        <div className="rounded-card border border-line p-4">
          <ProcessTimeline events={a.timeline} />
        </div>
      </Section>

      {/* Sticky decision bar */}
      {pending && (
        <div className="fixed inset-x-0 bottom-16 z-[var(--z-nav)] border-t border-line bg-bg/95 backdrop-blur md:bottom-0 md:left-[220px]">
          <div className="mx-auto flex max-w-[860px] flex-wrap items-center justify-end gap-3 px-4 py-3 md:px-8">
            {error ? (
              <p className="mr-auto text-[13px] text-negative">{error}</p>
            ) : (
              !a.can_approve && <p className="mr-auto text-[13px] text-muted">{a.blockers.join(" ")}</p>
            )}
            <Button variant="danger" disabled={busy} onClick={() => setRejecting(true)}>
              <X size={14} aria-hidden /> Reject
            </Button>
            <Tooltip label={a.can_approve ? `Approve exactly this order (version ${a.order_version}). Payment is the next step.` : a.blockers.join(" ")}>
              <Button
                variant="positive"
                className="h-10 px-5 text-[14px]"
                disabled={busy || !a.can_approve}
                onClick={() => act(() => apiPost<ApprovalView>(`/approvals/${a.id}/approve`, { order_hash: a.order_hash }))}
              >
                <SealCheck size={16} aria-hidden /> Approve {formatMoney(a.order.total, cur)}
              </Button>
            </Tooltip>
          </div>
        </div>
      )}

      <ItemDialog
        item={selected}
        currency={cur}
        editable={pending}
        busy={busy}
        onClose={() => setSelected(null)}
        onAction={(action, productId) => act(() => apiPost<ApprovalView>(`/approvals/${a.id}/items/${selected!.id}`, { action, product_id: productId ?? null }))}
      />

      <Dialog
        open={rejecting}
        onClose={() => setRejecting(false)}
        icon={<X size={16} />}
        title="Reject this order?"
        subtitle="Nothing will be bought. A reason helps PersonalIQ do better next time."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => {
                setRejecting(false);
                act(() => apiPost<ApprovalView>(`/approvals/${a.id}/reject`, { reason }));
              }}
            >
              Reject order
            </Button>
          </>
        }
      >
        <div className="flex flex-wrap gap-2">
          {REJECT_REASONS.map((r) => (
            <Chip key={r.value} selected={reason === r.value} onClick={() => setReason(reason === r.value ? null : r.value)}>
              {r.label}
            </Chip>
          ))}
        </div>
      </Dialog>
    </div>
  );
}

function Banner({ tone, icon, title, body, action }: { tone: "positive" | "negative" | "caution" | "neutral"; icon: React.ReactNode; title: string; body: string; action?: React.ReactNode }) {
  const cls = {
    positive: "border-positive/40 bg-positive/5 text-positive",
    negative: "border-negative/40 bg-negative/5 text-negative",
    caution: "border-caution/40 bg-caution/5 text-caution",
    neutral: "border-line text-muted",
  }[tone];
  return (
    <div className={cn("flex items-start gap-3 rounded-card border px-4 py-3", cls)}>
      <span className="mt-0.5 shrink-0" aria-hidden>
        {icon}
      </span>
      <div className="flex flex-col gap-1">
        <p className="text-[14px] font-semibold text-fg">{title}</p>
        <p className="text-[13px] text-muted">{body}</p>
        {action && <div className="text-[13px]">{action}</div>}
      </div>
    </div>
  );
}
