"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowsClockwise,
  CaretDown,
  ChartBar,
  ChartDonut,
  CheckCircle,
  Lightning,
  Scales,
  Sparkle,
  TrendUp,
  Wallet,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Field, inputClass } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { currencySymbol, formatMoney } from "@/lib/format";
import type { Affordability, FinanceBudget, FinanceOverview } from "@/types/finance";

const n = (s: string | null | undefined) => Number(s ?? 0);
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function FinanceView() {
  const [data, setData] = useState<FinanceOverview | null>(null);
  const [failed, setFailed] = useState(false);
  const [summary, setSummary] = useState<{ text: string; by_llm: boolean } | null>(null);

  useEffect(() => {
    apiGet<FinanceOverview>("/finance/overview")
      .then((d) => {
        setData(d);
        if (d.has_data) apiGet<{ text: string; by_llm: boolean }>("/finance/summary").then(setSummary).catch(() => setSummary({ text: "", by_llm: false }));
      })
      .catch(() => setFailed(true));
  }, []);

  const header = (
    <PageHeader
      icon={<ChartDonut size={18} />}
      title="Finance"
      description="Your spending, budgets and what you can afford. Every number is calculated from your data; nothing is estimated by AI."
    />
  );

  if (failed)
    return (
      <div className="flex max-w-[860px] flex-col gap-8">
        {header}
        <p className="text-[13px] text-negative">Couldn&apos;t load your finances. Check that the API is running.</p>
      </div>
    );
  if (!data)
    return (
      <div className="flex max-w-[860px] flex-col gap-8">
        {header}
        <div className="skeleton h-64 w-full" aria-busy="true" aria-label="Loading" />
      </div>
    );

  const cur = data.currency;
  return (
    <div className="flex max-w-[860px] flex-col gap-8 pb-16">
      {header}

      {!data.has_data ? (
        <EmptyState
          icon={<ChartBar size={20} />}
          title="No spending data yet"
          body="Upload a transactions CSV under You → Spending. Purchases you pay for with PayPal here are added automatically."
          action={
            <Link href="/you" className="text-[13px] font-medium text-fg underline underline-offset-4">
              Go to You
            </Link>
          }
        />
      ) : (
        <>
          <ThisMonth data={data} summary={summary} />
          <Months data={data} />
        </>
      )}

      <Section title="Budgets" description="Each order counts only against the budget it was planned with. Committed means approved but not paid yet." icon={<Wallet size={14} />}>
        {data.budgets.length ? (
          <ul className="flex flex-col gap-3">
            {data.budgets.map((b) => (
              <BudgetRow key={b.name} b={b} />
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-muted">No budgets yet. Set a monthly budget during onboarding under You.</p>
        )}
      </Section>

      <AffordCheck budgets={data.budgets} currency={cur} />

      {data.has_data && (
        <>
          <Categories data={data} />
          <Recurring data={data} />
          <Unusual data={data} />
        </>
      )}

      <p className="text-xs text-subtle">
        Based on {data.transaction_count} transactions from the last {data.window_days} days: {data.sources.uploaded} uploaded, {data.sources.paypal} from
        PayPal-verified purchases. Anything you haven&apos;t uploaded isn&apos;t known.
      </p>
    </div>
  );
}

// ---- This month: hero number + projection ----

function ThisMonth({ data, summary }: { data: FinanceOverview; summary: { text: string; by_llm: boolean } | null }) {
  const cur = data.currency;
  const fc = data.forecast;
  const avg = data.everyday_monthly_average;
  const vsAvg = avg ? Math.round(((n(fc.projected_total) - n(avg)) / n(avg)) * 100) : null;
  return (
    <section className="flex flex-col gap-4 rounded-card border border-line p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-subtle">Everyday spending in {fc.month}, so far</span>
          <span className="tabular text-3xl font-semibold tracking-tight text-fg">{formatMoney(fc.so_far, cur)}</span>
          <Tooltip label={fc.assumptions.join(" ")}>
            <span tabIndex={0} className="cursor-help text-[13px] text-muted underline decoration-dotted underline-offset-4">
              Heading for about {formatMoney(fc.projected_total, cur)} by month end
              {vsAvg !== null && ` (${vsAvg >= 0 ? "+" : ""}${vsAvg}% vs a usual month)`}
            </span>
          </Tooltip>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs text-subtle">
          <span>{fc.days_left} days left</span>
          {fc.recurring_due.length > 0 && <span>Still due: {fc.recurring_due.join(", ")}</span>}
        </div>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-3">
        {avg && <Stat label="Usual month" value={formatMoney(avg, cur)} />}
        <Stat label="Recurring / mo" value={formatMoney(data.recurring_monthly_total, cur)} />
        {n(data.planned_total) > 0 && <Stat label={`Planned (${data.window_days} d)`} value={formatMoney(data.planned_total, cur)} />}
      </div>
      {summary === null ? (
        <div className="skeleton h-10 w-full" aria-busy="true" aria-label="Writing a summary" />
      ) : (
        summary.text && (
          <div className="flex flex-col gap-1 rounded-card border border-line bg-surface px-4 py-3">
            <p className="text-[13px] leading-relaxed text-fg">{summary.text}</p>
            <span className="inline-flex items-center gap-1 text-xs text-subtle">
              <Sparkle size={12} aria-hidden />
              {summary.by_llm ? "Written by the language model from the numbers on this page. It doesn't calculate anything." : "Summary from the numbers on this page."}
            </span>
          </div>
        )
      )}
    </section>
  );
}

// ---- Monthly bars (everyday only; planned purchases would dwarf them) ----

function Months({ data }: { data: FinanceOverview }) {
  const cur = data.currency;
  const fc = data.forecast;
  const max = Math.max(...data.months.map((m) => n(m.everyday)), n(fc.projected_total), 1);
  return (
    <Section title="Month by month" description="Everyday spending. Planned purchases are listed under each month, not stacked, so they don't hide the rest." icon={<TrendUp size={14} />}>
      <div className="rounded-card border border-line p-4">
        <div className="grid h-40 grid-cols-4 items-end gap-4 border-b border-line" role="list" aria-label="Everyday spending per month">
          {data.months.map((m) => {
            const h = (n(m.everyday) / max) * 100;
            const projected = m.partial ? (n(fc.projected_total) / max) * 100 : 0;
            const label = m.partial
              ? `${m.label}: ${formatMoney(m.everyday, cur)} so far, about ${formatMoney(fc.projected_total, cur)} projected`
              : `${m.label}: ${formatMoney(m.everyday, cur)}`;
            return (
              <Tooltip key={m.month} label={label} className="h-full w-full">
                <span role="listitem" tabIndex={0} aria-label={label} className="relative flex h-full w-full cursor-help items-end justify-center">
                  {m.partial && (
                    <span className="absolute bottom-0 w-6 rounded-t-[4px] border border-b-0 border-line-strong" style={{ height: `${projected}%` }} aria-hidden />
                  )}
                  <span className={cn("relative w-6 rounded-t-[4px]", m.partial ? "bg-muted" : "bg-fg")} style={{ height: `${Math.max(h, 1)}%` }} aria-hidden />
                </span>
              </Tooltip>
            );
          })}
        </div>
        <div className="grid grid-cols-4 gap-4 pt-2 text-center">
          {data.months.map((m) => (
            <div key={m.month} className="flex flex-col gap-0.5">
              <span className="text-xs text-subtle">
                {m.label}
                {m.partial && " (so far)"}
              </span>
              <span className="tabular text-xs font-medium text-fg">{formatMoney(m.everyday, cur)}</span>
              {n(m.planned) > 0 && <span className="tabular text-[11px] text-subtle">+ {formatMoney(m.planned, cur)} planned</span>}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-subtle">The outline on the current month is the projected month end. Hover a bar for the figure.</p>
    </Section>
  );
}

// ---- Budgets ----

function BudgetRow({ b }: { b: FinanceBudget }) {
  const limit = n(b.limit) || 1;
  const spent = Math.min((n(b.spent) / limit) * 100, 100);
  const flight = Math.min((n(b.in_flight) / limit) * 100, 100 - spent);
  return (
    <li className="flex flex-col gap-2 rounded-card border border-line p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[13px] font-medium text-fg">
          {b.name} <span className="font-normal text-subtle">· {b.period_label}</span>
        </span>
        <span className={cn("tabular text-[13px]", b.over ? "font-semibold text-negative" : "text-fg")}>
          {b.over ? (
            <span className="inline-flex items-center gap-1">
              <WarningCircle size={14} weight="fill" aria-hidden /> Over by {formatMoney(String(-n(b.left)), b.currency)}
            </span>
          ) : (
            `${formatMoney(b.left, b.currency)} left`
          )}
        </span>
      </div>
      <Tooltip label={`Spent ${formatMoney(b.spent, b.currency)}, committed ${formatMoney(b.in_flight, b.currency)}, of ${formatMoney(b.limit, b.currency)}.`} className="w-full">
        <span tabIndex={0} className="flex h-2 w-full cursor-help gap-0.5 overflow-hidden rounded-full bg-surface-2" aria-label={`${b.used_pct}% used`}>
          {spent > 0 && <span className={cn("h-full rounded-full", b.over ? "bg-negative" : "bg-fg")} style={{ width: `${spent}%` }} />}
          {flight > 0 && <span className="h-full rounded-full bg-muted" style={{ width: `${flight}%` }} />}
        </span>
      </Tooltip>
      <div className="flex flex-wrap gap-x-4 text-xs text-subtle">
        <span>
          <span className="mr-1 inline-block size-2 rounded-full bg-fg align-middle" aria-hidden />
          Spent {formatMoney(b.spent, b.currency)}
        </span>
        <span>
          <span className="mr-1 inline-block size-2 rounded-full bg-muted align-middle" aria-hidden />
          Committed {formatMoney(b.in_flight, b.currency)}
        </span>
        <span>
          {b.used_pct}% of {formatMoney(b.limit, b.currency)}
        </span>
      </div>
    </li>
  );
}

// ---- Can I afford it? ----

function AffordCheck({ budgets, currency }: { budgets: FinanceBudget[]; currency: string }) {
  const monthly = budgets.find((b) => b.period === "monthly")?.name ?? budgets[0]?.name ?? "";
  const [amount, setAmount] = useState("");
  const [budget, setBudget] = useState(monthly);
  const [result, setResult] = useState<Affordability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const valid = /^\d+(\.\d{1,2})?$/.test(amount.trim()) && Number(amount) > 0;

  async function check() {
    if (!valid) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await apiPost<Affordability>("/finance/affordability", { amount: amount.trim(), budget_name: budget || null }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't check that.");
    } finally {
      setBusy(false);
    }
  }

  const tone = result && { fits: "positive", tight: "caution", over: "negative", unknown: "neutral" }[result.verdict];
  const verdict = result && {
    fits: { icon: <CheckCircle size={18} weight="fill" />, title: "Fits your budget" },
    tight: { icon: <WarningCircle size={18} weight="fill" />, title: "Fits, but it's tight" },
    over: { icon: <XCircle size={18} weight="fill" />, title: "Over budget" },
    unknown: { icon: <Scales size={18} />, title: "No budget to check against" },
  }[result.verdict];

  return (
    <Section title="Can I afford it?" description="Checks an amount against a budget and your usual month. Exact math, no guessing." icon={<Scales size={14} />}>
      <div className="flex flex-col gap-4 rounded-card border border-line p-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            check();
          }}
        >
          <Field label="Amount" htmlFor="afford-amount">
            <div className="relative w-40">
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[13px] text-subtle">{currencySymbol(currency)}</span>
              <input
                id="afford-amount"
                inputMode="decimal"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value.replace(/[^\d.]/g, ""));
                  setResult(null);
                }}
                className={cn(inputClass, "tabular pl-7")}
                placeholder="20000"
              />
            </div>
          </Field>
          {budgets.length > 0 && (
            <Field label="Against" htmlFor="afford-budget">
              <select
                id="afford-budget"
                value={budget}
                onChange={(e) => {
                  setBudget(e.target.value);
                  setResult(null);
                }}
                className={cn(inputClass, "w-56")}
              >
                {budgets.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Button type="submit" disabled={!valid || busy}>
            <Lightning size={14} aria-hidden /> {busy ? "Checking" : "Check"}
          </Button>
        </form>
        {error && <p className="text-[13px] text-negative">{error}</p>}
        {result && verdict && (
          <div
            className={cn(
              "flex items-start gap-3 rounded-card border px-4 py-3",
              tone === "positive" && "border-positive/40 bg-positive/5 text-positive",
              tone === "caution" && "border-caution/40 bg-caution/5 text-caution",
              tone === "negative" && "border-negative/40 bg-negative/5 text-negative",
              tone === "neutral" && "border-line text-muted",
            )}
          >
            <span className="mt-0.5 shrink-0" aria-hidden>
              {verdict.icon}
            </span>
            <div className="flex flex-col gap-1">
              <p className="text-[14px] font-semibold text-fg">
                {verdict.title}
                {result.left_after && <span className="font-normal text-muted"> · {formatMoney(result.left_after, currency)} left after</span>}
              </p>
              <ul className="flex flex-col gap-0.5 text-[13px] text-muted">
                {result.lines.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </Section>
  );
}

// ---- Categories ----

function Categories({ data }: { data: FinanceOverview }) {
  const [all, setAll] = useState(false);
  const cur = data.currency;
  const shown = all ? data.categories : data.categories.slice(0, 5);
  const max = Math.max(...data.categories.map((c) => n(c.total)), 1);
  return (
    <Section title="Where everyday money goes" description={`Last ${data.window_days} days. Change compares the last 30 days with the 30 before.`} icon={<ChartBar size={14} />}>
      <ul className="flex flex-col gap-3 rounded-card border border-line p-4">
        {shown.map((c) => (
          <li key={c.category} className="grid grid-cols-[7rem_minmax(0,1fr)_auto] items-center gap-3">
            <span className="truncate text-[13px] text-fg">{c.category}</span>
            <Tooltip label={`${c.count} payments, ${c.share_pct}% of everyday spending. Last 30 days ${formatMoney(c.last_30, cur)}, the 30 before ${formatMoney(c.prior_30, cur)}.`} className="w-full">
              <span tabIndex={0} className="flex h-5 w-full cursor-help items-center">
                <span className="h-2 rounded-r-[4px] bg-fg" style={{ width: `${Math.max((n(c.total) / max) * 100, 1)}%` }} aria-hidden />
              </span>
            </Tooltip>
            <span className="tabular flex w-40 items-baseline justify-end gap-2 text-[13px]">
              <span className="font-medium text-fg">{formatMoney(c.total, cur)}</span>
              <span className="w-12 text-right text-xs text-subtle">
                {c.change_pct === null ? "new" : `${c.change_pct > 0 ? "+" : ""}${c.change_pct}%`}
              </span>
            </span>
          </li>
        ))}
      </ul>
      {data.categories.length > 5 && !all && (
        <button type="button" onClick={() => setAll(true)} className="flex h-9 w-fit items-center gap-1.5 text-[13px] font-medium text-muted hover:text-fg">
          <CaretDown size={12} aria-hidden /> Show {data.categories.length - 5} more
        </button>
      )}
    </Section>
  );
}

// ---- Recurring and unusual ----

function Recurring({ data }: { data: FinanceOverview }) {
  const cur = data.currency;
  return (
    <Section
      title={`Recurring payments (${data.recurring.length})`}
      description="Same merchant, nearly the same amount, at a steady weekly or monthly rhythm, seen at least 3 times."
      icon={<ArrowsClockwise size={14} />}
    >
      {data.recurring.length ? (
        <ul className="overflow-hidden rounded-card border border-line">
          {data.recurring.map((r) => (
            <li key={r.merchant} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium text-fg">{r.merchant}</span>
                <span className="truncate text-xs text-subtle">
                  {r.cadence === "monthly" ? "Monthly" : "Weekly"} · {r.category} · seen {r.times_seen} times · next around {day(r.next_expected)}
                </span>
              </span>
              <span className="tabular text-[13px] font-medium text-fg">{formatMoney(r.amount, cur)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-muted">None found. Upload a few months of transactions to spot subscriptions.</p>
      )}
    </Section>
  );
}

function Unusual({ data }: { data: FinanceOverview }) {
  const cur = data.currency;
  return (
    <Section title={`Unusual payments (${data.unusual.length})`} description="More than twice what you usually spend in that category (categories with at least 3 payments)." icon={<WarningCircle size={14} />}>
      {data.unusual.length ? (
        <ul className="overflow-hidden rounded-card border border-line">
          {data.unusual.map((u) => (
            <li key={`${u.on}-${u.merchant}-${u.amount}`} className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium text-fg">{u.merchant}</span>
                <span className="truncate text-xs text-subtle">
                  {day(u.on)} · {u.category} · {u.times_usual}× your usual {formatMoney(u.usual, cur)}
                </span>
              </span>
              <span className="tabular text-[13px] font-medium text-fg">{formatMoney(u.amount, cur)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-muted">Nothing out of the ordinary in the last {data.window_days} days.</p>
      )}
    </Section>
  );
}
