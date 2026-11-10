"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  CalendarCheck,
  CaretDown,
  CaretRight,
  ChatCircleText,
  Check,
  Info,
  Package,
  Prohibit,
  Receipt,
  ShieldCheck,
  Star,
  TreeStructure,
  Wallet,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { CategoryIcon } from "@/components/ui/category-icon";
import { Dialog } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { FeedbackDialog } from "@/components/you/feedback-section";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";
import type { FollowUp, Receipt as ReceiptData, ReceiptItem } from "@/types/receipt";
import { shortDate } from "./purchases-view";
import { RECEIPT_STATE, ReceiptStateBadge } from "./receipt-state";

const SHOW = 5;
const ASPECT_WORD: Record<string, string> = { quality: "quality", durability: "durability", value: "value" };
const SCALE_WORD: Record<number, string> = { 2: "poor", 4: "weak", 6: "OK", 8: "good", 10: "great" };

export function ReceiptView({ orderId }: { orderId: string }) {
  const [r, setR] = useState<ReceiptData | null>(null);
  const [failed, setFailed] = useState(false);
  const [item, setItem] = useState<ReceiptItem | null>(null);
  const [rating, setRating] = useState<FollowUp | null>(null);
  const [allItems, setAllItems] = useState(false);

  const load = useCallback(() => {
    apiGet<ReceiptData>(`/orders/${orderId}/receipt`).then(setR).catch(() => setFailed(true));
  }, [orderId]);
  useEffect(load, [load]);

  if (failed) return <p className="text-[13px] text-negative">Couldn&apos;t load this receipt. Check that the API is running.</p>;
  if (!r) return <div className="skeleton h-64 w-full max-w-[860px]" aria-busy="true" aria-label="Loading" />;

  const cur = r.totals.currency;
  const paid = r.state === "paid";
  const charge = r.totals.charge;
  const followBy = Object.fromEntries(r.follow_up.items.map((f) => [f.product_id, f]));
  const shownItems = allItems ? r.items : r.items.slice(0, SHOW);
  const rated = r.follow_up.items.filter((f) => f.feedback).length;

  return (
    <div className="flex max-w-[860px] flex-col gap-8 pb-16">
      <PageHeader
        icon={<Receipt size={18} />}
        title={r.request.objective || "Decision receipt"}
        description="Decision receipt: what you asked for, how each pick was made, what you approved, and what PayPal confirmed."
        actions={<ReceiptStateBadge state={r.state} large />}
      />

      {/* Summary */}
      <section className="flex flex-col gap-4 rounded-card border border-line p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-subtle">{paid ? "Paid" : "Order total"}, shipping included</span>
            <span className="tabular text-3xl font-semibold tracking-tight text-fg">{formatMoney(r.totals.total, cur)}</span>
            {charge.currency !== cur && (
              <span className="text-[13px] text-muted">
                {paid ? "Charged" : "PayPal charges"} {formatMoney(charge.total, charge.currency)} {charge.currency}. {charge.rate_note}.
              </span>
            )}
          </div>
          <p className="max-w-[34ch] text-right text-xs text-subtle">{RECEIPT_STATE[r.state].hint}</p>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-3">
          <Stat label="Items" value={String(r.items.length)} />
          <Stat label="Shipping" value={Number(r.totals.shipping) === 0 ? "Free" : formatMoney(r.totals.shipping, cur)} />
          {r.approval.approved_at && <Stat label="Approved" value={shortDate(r.approval.approved_at)} />}
          {r.completed_at && <Stat label="Completed" value={new Date(r.completed_at).toLocaleString()} />}
          <Stat label="Order" value={r.order_id.slice(0, 8)} />
        </div>
      </section>

      <Section title="Your request" description="In your words, and what it was understood as." icon={<ChatCircleText size={14} />}>
        <div className="flex flex-col gap-2 rounded-card border border-line p-4">
          <p className="text-[14px] text-fg">&ldquo;{r.request.message}&rdquo;</p>
          <p className="text-xs text-subtle">
            {r.request.at && `${shortDate(r.request.at)} · `}Read by {r.request.understood_by === "nemotron" ? "Nemotron, checked by rules" : "built-in rules"}.
          </p>
        </div>
      </Section>

      <Section title="How it was decided" description="Each agent's step, in order. Money math is done by code, not the language model." icon={<TreeStructure size={14} />}>
        {r.agents.length ? (
          <ol className="flex flex-col rounded-card border border-line">
            {r.agents.map((a, i) => (
              <li key={`${a.agent}-${i}`} className="flex gap-3 border-b border-line px-4 py-3 last:border-b-0">
                <span className="tabular mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border border-line text-[11px] text-subtle">{i + 1}</span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-[13px] font-medium text-fg">{a.title}</span>
                    {a.duration_ms != null && <span className="tabular text-xs text-subtle">{a.duration_ms} ms</span>}
                  </span>
                  <span className="text-[13px] leading-relaxed text-muted">{a.explanation}</span>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[13px] text-muted">No agent record for this order.</p>
        )}
      </Section>

      <Section
        title={`What was bought, and why (${r.items.length})`}
        description={`${r.research.candidates_considered} options were compared across ${r.research.ranked_needs} needs. Open an item for the alternatives it beat.`}
        icon={<Package size={14} />}
      >
        <ul className="overflow-hidden rounded-card border border-line">
          {shownItems.map((i) => (
            <li key={i.id} className="border-b border-line last:border-b-0">
              <button onClick={() => setItem(i)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface">
                <span className="grid size-8 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">
                  <CategoryIcon category={i.category} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13px] font-medium text-fg">
                    {i.name}
                    {i.quantity > 1 && <span className="text-subtle"> × {i.quantity}</span>}
                  </span>
                  <span className="truncate text-xs text-subtle">{i.reason || `${needLabel(i.need)} · ${i.merchant}`}</span>
                </span>
                {followBy[i.product_id]?.feedback && (
                  <Tooltip label="You rated this">
                    <span tabIndex={0} className="tabular inline-flex h-6 shrink-0 cursor-help items-center gap-1 rounded-full border border-line px-2 text-xs text-muted">
                      <Star size={12} weight="fill" aria-hidden /> {followBy[i.product_id].feedback!.rating}/10
                    </span>
                  </Tooltip>
                )}
                <span className="tabular w-28 shrink-0 text-right text-[13px] font-medium text-fg">{formatMoney(i.line_total, cur)}</span>
                <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
        {r.items.length > SHOW && !allItems && (
          <button type="button" onClick={() => setAllItems(true)} className="flex h-9 w-fit items-center gap-1.5 text-[13px] font-medium text-muted hover:text-fg">
            <CaretDown size={12} aria-hidden /> Show {r.items.length - SHOW} more
          </button>
        )}
      </Section>

      {(r.research.excluded.length > 0 || r.research.skipped_needs.length > 0) && (
        <Section title="Ruled out" description="What was deliberately left out, so you can check the reasoning." icon={<Prohibit size={14} />}>
          <ul className="flex flex-col rounded-card border border-line">
            {r.research.excluded.map((x) => (
              <li key={x.product_id} className="flex items-start justify-between gap-3 border-b border-line px-4 py-2.5 last:border-b-0">
                <span className="text-[13px] text-fg">{x.name}</span>
                <span className="text-right text-xs text-muted">{x.reasons.join("; ")}</span>
              </li>
            ))}
            {r.research.skipped_needs.map((s) => (
              <li key={s.need} className="flex items-start justify-between gap-3 border-b border-line px-4 py-2.5 last:border-b-0">
                <span className="text-[13px] text-fg">{needLabel(s.need)} (whole need)</span>
                <span className="text-right text-xs text-muted">{s.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Budget check" description="Done by Financial Autopilot with exact decimal math." icon={<Wallet size={14} />}>
        <div className="flex flex-col gap-3 rounded-card border border-line p-4">
          <p className={cn("text-[13px]", r.financial.within_budget === false ? "text-negative" : "text-fg")}>{r.financial.explanation || "No budget was set for this request."}</p>
          {(r.financial.limit || r.financial.remaining_after) && (
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {r.financial.limit && <Stat label="Budget" value={formatMoney(r.financial.limit, cur)} />}
              {r.financial.remaining_after && <Stat label="Left after" value={formatMoney(r.financial.remaining_after, cur)} />}
              {r.financial.used_pct != null && <Stat label="Used" value={`${r.financial.used_pct}%`} />}
            </div>
          )}
        </div>
      </Section>

      <Section title="Approval and payment" description="Your approval covered this exact version. Paid means PayPal confirmed the capture." icon={<ShieldCheck size={14} />}>
        <dl className="grid gap-x-6 gap-y-3 rounded-card border border-line p-4 text-[13px] sm:grid-cols-2">
          <Row label="Approved by">{r.approval.approved ? `You, ${shortDate(r.approval.approved_at)}` : "Not approved"}</Row>
          <Row label="Version approved">
            {r.approval.version ? (
              <Tooltip label="A fingerprint of the items, prices, totals and charge. Any change would have voided the approval.">
                <span tabIndex={0} className="cursor-help">
                  v{r.approval.version} · <span className="font-mono text-xs">{r.approval.fingerprint}</span>
                </span>
              </Tooltip>
            ) : (
              "None"
            )}
          </Row>
          <Row label="PayPal order">{r.payment.paypal_order_id ? <span className="font-mono text-xs">{r.payment.paypal_order_id}</span> : "Not created"}</Row>
          <Row label="PayPal capture">{r.payment.capture_id ? <span className="font-mono text-xs">{r.payment.capture_id}</span> : "None"}</Row>
          <Row label="Status">
            <span className={cn(paid ? "text-positive" : r.state === "payment_failed" ? "text-negative" : "text-fg")}>
              {paid ? `Verified, ${r.payment.capture_status?.toLowerCase()}` : RECEIPT_STATE[r.state].label}
            </span>
          </Row>
          <Row label="Charged">{r.payment.verified && r.payment.amount ? `${formatMoney(r.payment.amount, r.payment.currency ?? charge.currency)} ${r.payment.currency}` : "Nothing yet"}</Row>
        </dl>
        {!paid && r.state !== "not_bought" && (
          <p className="text-xs text-subtle">
            Pay from the{" "}
            <Link href="/approvals" className="font-medium text-fg underline underline-offset-4">
              approval page
            </Link>
            .
          </p>
        )}
      </Section>

      {paid && (
        <Section
          title="Follow-up"
          description={`${rated} of ${r.follow_up.items.length} items rated. ${r.follow_up.delivery_note}`}
          icon={<CalendarCheck size={14} />}
        >
          <FollowUps items={r.follow_up.items} onRate={setRating} />
        </Section>
      )}

      <Section title="About this receipt" icon={<Info size={14} />}>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-subtle">
          {r.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </Section>

      <ItemDialog item={item} cur={cur} follow={item ? followBy[item.product_id] : undefined} onClose={() => setItem(null)} onRate={(f) => { setItem(null); setRating(f); }} />

      {rating && (
        <FeedbackDialog
          fixed={{ productId: rating.product_id, name: rating.name, orderId: r.order_id }}
          onClose={() => setRating(null)}
          onDone={() => {
            setRating(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="text-fg">{children}</dd>
    </div>
  );
}

function FollowUps({ items, onRate }: { items: FollowUp[]; onRate: (f: FollowUp) => void }) {
  const [all, setAll] = useState(false);
  // Unrated first, so the prompt is at the top.
  const sorted = [...items].sort((a, b) => Number(!!a.feedback) - Number(!!b.feedback) || a.return_by.localeCompare(b.return_by));
  const shown = all ? sorted : sorted.slice(0, SHOW);
  return (
    <div className="flex flex-col gap-2">
      <ul className="overflow-hidden rounded-card border border-line">
        {shown.map((f) => (
          <li key={f.item_id} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-[13px] font-medium text-fg">{f.name}</span>
              <span className="truncate text-xs text-subtle">
                Return by {shortDate(f.return_by)}
                {f.warranty_until && ` · warranty to ${shortDate(f.warranty_until)}`}
                {f.feedback?.aspects && Object.keys(f.feedback.aspects).length > 0 &&
                  ` · ${Object.entries(f.feedback.aspects).map(([k, v]) => `${ASPECT_WORD[k] ?? k} ${SCALE_WORD[v] ?? `${v}/10`}`).join(", ")}`}
              </span>
            </span>
            {f.feedback ? (
              <span className="inline-flex h-6 shrink-0 items-center gap-1 rounded-full border border-positive/40 px-2 text-xs font-semibold text-positive">
                <Check size={12} aria-hidden /> Rated {f.feedback.rating}/10
              </span>
            ) : (
              <Tooltip label="Once you've used it: how did it turn out? Low ratings change what gets picked next time.">
                <Button variant="secondary" onClick={() => onRate(f)}>
                  <Star size={14} aria-hidden /> Rate
                </Button>
              </Tooltip>
            )}
          </li>
        ))}
      </ul>
      {sorted.length > SHOW && !all && (
        <button type="button" onClick={() => setAll(true)} className="flex h-9 w-fit items-center gap-1.5 text-[13px] font-medium text-muted hover:text-fg">
          <CaretDown size={12} aria-hidden /> Show {sorted.length - SHOW} more
        </button>
      )}
      <p className="text-xs text-subtle">Return windows and warranties come from the demo catalog, counted from the payment date.</p>
    </div>
  );
}

function ItemDialog({ item, cur, follow, onClose, onRate }: { item: ReceiptItem | null; cur: string; follow?: FollowUp; onClose: () => void; onRate: (f: FollowUp) => void }) {
  if (!item) return null;
  return (
    <Dialog
      open
      onClose={onClose}
      icon={<CategoryIcon category={item.category} />}
      title={item.name}
      subtitle={`${needLabel(item.need)} · ${item.merchant}`}
      footer={
        follow && !follow.feedback ? (
          <Button variant="secondary" onClick={() => onRate(follow)}>
            <Star size={14} aria-hidden /> Rate this item
          </Button>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-5 text-[13px]">
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <Stat label="Paid" value={formatMoney(item.line_total, cur)} />
          {item.quantity > 1 && <Stat label="Qty" value={String(item.quantity)} />}
          {item.score != null && <Stat label="Match" value={item.score.toFixed(1)} />}
          {item.rank != null && <Stat label="Rank" value={`#${item.rank}`} />}
        </div>
        <Block label="Why this one">{item.reason || "Best fit within the budget."}</Block>
        {item.your_decision && <Block label="Your decision">{item.your_decision === "kept" ? "You reviewed it and kept it." : "You swapped to this one yourself."}</Block>}
        <Block label="Alternatives it beat">
          {item.alternatives.length ? (
            <ul className="flex flex-col gap-2">
              {item.alternatives.map((a) => (
                <li key={a.name} className="flex flex-col rounded-control border border-line px-3 py-2">
                  <span className="font-medium text-fg">{a.name}</span>
                  <span className="text-xs text-muted">{a.why_not}</span>
                </li>
              ))}
            </ul>
          ) : (
            "No other option was in the running for this need."
          )}
        </Block>
        {follow && (
          <Block label="Follow-up">
            Return by {shortDate(follow.return_by)} ({follow.return_window_days}-day window)
            {follow.warranty_until ? `. Warranty until ${shortDate(follow.warranty_until)}.` : ". No warranty listed."}
            {follow.feedback && ` You rated it ${follow.feedback.rating}/10${follow.feedback.didnt_work ? `: ${follow.feedback.didnt_work}` : ""}.`}
          </Block>
        )}
      </div>
    </Dialog>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-subtle">{label}</span>
      <div className="text-fg">{children}</div>
    </div>
  );
}
