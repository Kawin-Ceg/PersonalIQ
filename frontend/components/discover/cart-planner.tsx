"use client";

import { useEffect, useMemo, useState } from "react";
import { CaretDown, CheckCircle, ListChecks, Plus, ShoppingCart, Truck, Wallet, WarningCircle, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { CategoryIcon } from "@/components/ui/category-icon";
import { Dialog } from "@/components/ui/dialog";
import { Chip } from "@/components/ui/field";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { currencySymbol, formatMoney, needLabel } from "@/lib/format";
import type { CartPlan, NeedOption, UserContext } from "@/types/api";
import { ProductDialog, type ProductView } from "./product-dialog";

type Pick = { need: string; required: boolean };

// A starting point for the demo; every need can be changed.
const APARTMENT_PRESET: Pick[] = [
  ...["mattress", "bed_frame", "sheets", "pillows", "cookware"].map((need) => ({ need, required: true })),
  ...["sofa", "dining", "desk", "office_chair", "microwave", "kettle", "vacuum", "towels", "curtains"].map((need) => ({ need, required: false })),
];
const LINES_SHOWN = 6;

export function CartPlanner() {
  const [needs, setNeeds] = useState<NeedOption[]>([]);
  const [ctx, setCtx] = useState<UserContext | null>(null);
  const [picks, setPicks] = useState<Pick[]>(APARTMENT_PRESET);
  const [budget, setBudget] = useState("");
  const [budgetName, setBudgetName] = useState<string | null>(null);
  const [plan, setPlan] = useState<CartPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    apiGet<NeedOption[]>("/products/needs").then(setNeeds).catch(() => setError("Couldn't load the catalog."));
    apiGet<UserContext>("/me/context")
      .then((c) => {
        setCtx(c);
        const first = c.budgets.find((b) => b.period === "one_off") ?? c.budgets[0];
        if (first) {
          setBudget(first.limit_amount.replace(/\.00$/, ""));
          setBudgetName(first.name);
        }
      })
      .catch(() => {});
  }, []);

  const currency = ctx?.currency ?? "USD";
  const budgetValid = /^\d{1,9}(\.\d{1,2})?$/.test(budget.trim()) && Number(budget) > 0;
  const must = picks.filter((p) => p.required);
  const nice = picks.filter((p) => !p.required);

  const flip = (need: string) => setPicks((ps) => ps.map((p) => (p.need === need ? { ...p, required: !p.required } : p)));
  const remove = (need: string) => setPicks((ps) => ps.filter((p) => p.need !== need));
  const toggleAdd = (need: string) =>
    setPicks((ps) => (ps.some((p) => p.need === need) ? ps.filter((p) => p.need !== need) : [...ps, { need, required: false }]));

  async function build() {
    if (!budgetValid || picks.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(await apiPost<CartPlan>("/cart/optimize", { budget: budget.trim(), needs: picks, budget_name: budgetName }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't build the cart");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-[860px] flex-col gap-8">
      <Section title="Budget" description="The total, shipping included, must fit inside this." icon={<Wallet size={14} />}>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex h-10 w-48 items-center gap-2 rounded-control border border-line bg-surface px-3 focus-within:border-line-strong">
            <span className="text-[14px] text-muted">{currencySymbol(currency)}</span>
            <span className="sr-only">Budget in {currency}</span>
            <input
              inputMode="decimal"
              value={budget}
              onChange={(e) => {
                setBudget(e.target.value);
                setBudgetName(null);
              }}
              aria-invalid={!budgetValid}
              className="tabular h-full w-full bg-transparent text-[14px] text-fg outline-none"
            />
            <span className="text-xs text-subtle">{currency}</span>
          </label>
          {ctx?.budgets.map((b) => (
            <Tooltip key={b.name} label={`Use your ${b.name} budget (${formatMoney(b.limit_amount, b.currency)}) and check the cart against it.`}>
              <Chip
                selected={budgetName === b.name}
                onClick={() => {
                  setBudget(b.limit_amount.replace(/\.00$/, ""));
                  setBudgetName(b.name);
                }}
              >
                {b.name}
              </Chip>
            </Tooltip>
          ))}
        </div>
        {!budgetValid && budget !== "" && <p className="text-xs text-negative">Enter an amount like 169000 or 1999.99.</p>}
      </Section>

      <Section
        title="What you need"
        description="Click an item to move it between the two groups."
        icon={<ListChecks size={14} />}
        action={
          <Button variant="secondary" onClick={() => setAdding(true)}>
            <Plus size={14} aria-hidden /> Add needs
          </Button>
        }
      >
        <div className="flex flex-col gap-4 rounded-card border border-line p-4">
          <NeedGroup
            title="Must have"
            hint="Always included. If they don't fit the budget, PersonalIQ tells you instead of skipping them."
            picks={must}
            onFlip={flip}
            onRemove={remove}
          />
          <div className="border-t border-line" />
          <NeedGroup title="Nice to have" hint="Included when the budget allows. Dropped first if money runs short." picks={nice} onFlip={flip} onRemove={remove} />
        </div>
        <button type="button" onClick={() => setPicks(APARTMENT_PRESET)} className="w-fit text-[13px] text-muted underline-offset-4 hover:text-fg hover:underline">
          Reset to apartment essentials
        </button>
      </Section>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={build} disabled={busy || !budgetValid || picks.length === 0} className="h-10 px-5 text-[14px]">
          <ShoppingCart size={16} aria-hidden />
          {busy ? "Building your cart" : "Build cart"}
        </Button>
        {error && <p className="text-[13px] text-negative">{error}</p>}
      </div>

      {plan && <PlanView plan={plan} />}

      <Dialog open={adding} onClose={() => setAdding(false)} title="Add needs" subtitle="Pick anything you need. New items start as nice to have." icon={<Plus size={16} />} footer={<Button variant="positive" onClick={() => setAdding(false)}>Done</Button>}>
        <NeedPicker needs={needs} picks={picks} onToggle={toggleAdd} />
      </Dialog>
    </div>
  );
}

function NeedGroup({ title, hint, picks, onFlip, onRemove }: { title: string; hint: string; picks: Pick[]; onFlip: (n: string) => void; onRemove: (n: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <Tooltip label={hint} side="right" className="w-fit">
        <p tabIndex={0} className="cursor-help text-xs font-semibold text-muted">
          {title} <span className="tabular font-normal text-subtle">{picks.length}</span>
        </p>
      </Tooltip>
      {picks.length === 0 ? (
        <p className="text-[13px] text-subtle">None</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {picks.map((p) => (
            <span key={p.need} className={cn("flex h-8 items-center rounded-full border pl-3 pr-1 text-[13px] font-medium", p.required ? "border-line-strong bg-surface-2 text-fg" : "border-line text-muted")}>
              <button type="button" onClick={() => onFlip(p.need)} className="hover:text-fg">
                {needLabel(p.need)}
              </button>
              <Tooltip label="Remove">
                <button type="button" aria-label={`Remove ${needLabel(p.need)}`} onClick={() => onRemove(p.need)} className="ml-1 grid size-6 place-items-center rounded-full text-subtle hover:bg-negative/10 hover:text-negative">
                  <X size={12} />
                </button>
              </Tooltip>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function NeedPicker({ needs, picks, onToggle }: { needs: NeedOption[]; picks: Pick[]; onToggle: (n: string) => void }) {
  const byCategory = useMemo(() => {
    const m = new Map<string, NeedOption[]>();
    for (const n of needs) m.set(n.category, [...(m.get(n.category) ?? []), n]);
    return [...m.entries()];
  }, [needs]);
  return (
    <div className="flex flex-col gap-5">
      {byCategory.map(([cat, list]) => (
        <div key={cat} className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-[13px] font-semibold text-fg">
            <span className="text-muted">
              <CategoryIcon category={cat} />
            </span>
            {cat}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {list.map((n) => (
              <Chip key={n.need} selected={picks.some((p) => p.need === n.need)} onClick={() => onToggle(n.need)}>
                {needLabel(n.need)}
              </Chip>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function PlanView({ plan }: { plan: CartPlan }) {
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<ProductView | null>(null);
  const ev = plan.budget_evaluation;
  const ok = plan.feasible && (ev ? ev.within_budget : true);
  const lines = showAll ? plan.lines : plan.lines.slice(0, LINES_SHOWN);

  return (
    <Section title="Your cart" description="Picked to give you the best total score within budget. Click an item for details." icon={<ShoppingCart size={14} />}>
      <div className={cn("flex items-start gap-3 rounded-card border px-4 py-3", ok ? "border-positive/40 bg-positive/5" : "border-negative/40 bg-negative/5")}>
        {ok ? <CheckCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-positive" aria-hidden /> : <WarningCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-negative" aria-hidden />}
        <div className="flex flex-col gap-1">
          <p className="text-[14px] font-medium text-fg">{plan.message}</p>
          {ev && <p className="text-[13px] text-muted">{ev.explanation}</p>}
          {plan.lines.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
              <Stat label="Items" value={String(plan.lines.length)} />
              <Stat label="Total" value={formatMoney(plan.total, plan.currency)} />
              <Stat label="Left" value={formatMoney(plan.remaining, plan.currency)} />
              {ev && <Stat label="Budget used" value={`${ev.used_pct}%`} />}
            </div>
          )}
        </div>
      </div>

      {plan.lines.length > 0 && (
        <div className="overflow-hidden rounded-card border border-line">
          {lines.map((l) => (
            <button
              key={l.product.id}
              onClick={() => setSelected({ product: l.product, score: l.score, note: l.reason })}
              className="flex w-full items-center gap-3 border-b border-line px-4 py-3 text-left last:border-b-0 hover:bg-surface"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">
                <CategoryIcon category={l.product.category} />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium text-fg">
                  {l.product.name}
                  {l.quantity > 1 && <span className="text-muted"> x{l.quantity}</span>}
                </span>
                <span className="truncate text-xs text-subtle">
                  {needLabel(l.need)} · {l.product.merchant.name}
                </span>
              </span>
              <span className="tabular shrink-0 text-[13px] font-medium text-fg">{formatMoney(l.line_total, plan.currency)}</span>
            </button>
          ))}
          {plan.lines.length > LINES_SHOWN && (
            <button type="button" onClick={() => setShowAll(!showAll)} className="flex h-10 w-full items-center gap-1.5 px-4 text-[13px] font-medium text-muted hover:bg-surface hover:text-fg">
              <CaretDown size={12} className={showAll ? "rotate-180" : ""} aria-hidden />
              {showAll ? "Show fewer" : `Show all ${plan.lines.length} items`}
            </button>
          )}
        </div>
      )}

      {plan.skipped.length > 0 && (
        <div className="flex flex-col gap-1.5 rounded-card border border-line px-4 py-3">
          <p className="text-xs font-semibold text-muted">Not included</p>
          {plan.skipped.map((s) => (
            <p key={s.need} className="text-[13px] text-muted">
              <span className="text-fg">{needLabel(s.need)}</span>: {s.reason}
            </p>
          ))}
        </div>
      )}

      {plan.lines.length > 0 && (
        <dl className="flex flex-col gap-1.5 rounded-card border border-line p-4 text-[13px]">
          <Row label="Items" value={formatMoney(plan.subtotal, plan.currency)} />
          {plan.shipping.map((s) => (
            <Row key={s.merchant} icon={<Truck size={12} />} label={s.merchant} hint={s.note} value={Number(s.shipping) === 0 ? "Free" : formatMoney(s.shipping, plan.currency)} muted />
          ))}
          <Row label="Tax" hint={plan.tax_note} value="-" muted />
          <div className="my-1 border-t border-line" />
          <Row label="Total" value={formatMoney(plan.total, plan.currency)} strong />
          <Row label="Left from budget" value={formatMoney(plan.remaining, plan.currency)} muted />
        </dl>
      )}

      <ProductDialog view={selected} onClose={() => setSelected(null)} />
    </Section>
  );
}

function Row({ label, value, hint, icon, muted, strong }: { label: string; value: string; hint?: string; icon?: React.ReactNode; muted?: boolean; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className={cn("flex items-center gap-1.5", muted ? "text-muted" : "text-fg")}>
        {icon}
        {label}
        {hint && <span className="text-xs text-subtle">{hint}</span>}
      </dt>
      <dd className={cn("tabular", strong ? "text-[15px] font-semibold text-fg" : muted ? "text-muted" : "text-fg")}>{value}</dd>
    </div>
  );
}
