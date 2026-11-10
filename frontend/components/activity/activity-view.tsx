"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  CheckCircle,
  CircleDashed,
  ClockCounterClockwise,
  HourglassMedium,
  ListChecks,
  MinusCircle,
  Question,
  SealCheck,
  ShoppingCart,
  Sparkle,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";
import { ProductDialog, type ProductView } from "@/components/discover/product-dialog";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Select } from "@/components/ui/select";
import { Stat } from "@/components/ui/stat";
import { StatusPill } from "@/components/ui/status-pill";
import { useWorkflow } from "@/hooks/use-workflow";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";
import type { AgentRun, Workflow, WorkflowSummary } from "@/types/api";
import { AGENTS, STEPS } from "./agent-meta";
import { StepDialog } from "./step-dialog";

export function ActivityView() {
  const params = useSearchParams();
  const router = useRouter();
  const [recent, setRecent] = useState<WorkflowSummary[] | null>(null);
  const id = params.get("w") ?? recent?.[0]?.id ?? null;
  const { wf, error } = useWorkflow(id);

  useEffect(() => {
    apiGet<WorkflowSummary[]>("/workflows").then(setRecent).catch(() => setRecent([]));
  }, [wf?.status]);

  if (recent && recent.length === 0 && !params.get("w")) {
    return (
      <div className="flex max-w-[860px] flex-col gap-8">
        <PageHeader icon={<ClockCounterClockwise size={18} />} title="Activity" description="A live timeline of what each agent does for your request." />
        <EmptyState
          icon={<Sparkle size={20} />}
          title="Nothing running yet"
          body="Make a request on Home, like setting up a new apartment. You'll see each agent's work here as it happens."
          action={
            <Link href="/" className="text-[13px] font-medium text-fg underline underline-offset-4">
              Go to Home
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex max-w-[860px] flex-col gap-8">
      <PageHeader
        icon={<ClockCounterClockwise size={18} />}
        title="Activity"
        description="What each agent did for your request, live. Click a step to see its details."
        actions={
          recent && recent.length > 1 && id ? (
            <Select<string>
              label="Request"
              value={id}
              onChange={(v) => router.push(`/activity?w=${v}`)}
              options={recent.map((r) => ({ value: r.id, label: r.objective.length > 40 ? `${r.objective.slice(0, 40)}...` : r.objective }))}
              className="w-full max-w-72"
            />
          ) : undefined
        }
      />

      {error && <p className="text-[13px] text-negative">Couldn&apos;t load this request. Check that the API is running.</p>}
      {!wf && !error && <div className="skeleton h-40 w-full" aria-busy="true" aria-label="Loading" />}
      {wf && (
        <>
          <Outcome wf={wf} />
          <Timeline wf={wf} />
        </>
      )}
    </div>
  );
}

function Outcome({ wf }: { wf: Workflow }) {
  const [showCart, setShowCart] = useState(false);
  const [product, setProduct] = useState<ProductView | null>(null);
  const cart = wf.result.cart;
  const done = wf.runs.filter((r) => r.finished_at).length;

  const tone = {
    running: "border-line",
    awaiting_approval: "border-positive/40 bg-positive/5",
    needs_input: "border-caution/40 bg-caution/5",
    blocked: "border-negative/40 bg-negative/5",
    failed: "border-negative/40 bg-negative/5",
    approved: "border-positive/40 bg-positive/5",
    rejected: "border-line",
    paid: "border-positive/40 bg-positive/5",
    cancelled: "border-line",
    expired: "border-negative/40 bg-negative/5",
    reconciliation_required: "border-caution/40 bg-caution/5",
  }[wf.status];
  const icon = {
    running: <HourglassMedium size={20} className="text-muted" />,
    awaiting_approval: <CheckCircle size={20} weight="fill" className="text-positive" />,
    needs_input: <Question size={20} weight="fill" className="text-caution" />,
    blocked: <WarningCircle size={20} weight="fill" className="text-negative" />,
    failed: <XCircle size={20} weight="fill" className="text-negative" />,
    approved: <SealCheck size={20} weight="fill" className="text-positive" />,
    rejected: <XCircle size={20} className="text-muted" />,
    paid: <CheckCircle size={20} weight="fill" className="text-positive" />,
    cancelled: <XCircle size={20} className="text-muted" />,
    expired: <XCircle size={20} weight="fill" className="text-negative" />,
    reconciliation_required: <WarningCircle size={20} weight="fill" className="text-caution" />,
  }[wf.status];

  return (
    <div className={cn("flex flex-col gap-3 rounded-card border p-4", tone)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 shrink-0" aria-hidden>
            {icon}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <p className="text-xs text-subtle">&ldquo;{wf.intent.message}&rdquo;</p>
            <p className="text-[14px] font-medium leading-relaxed text-fg">
              {wf.status === "running" ? `Working on it. ${done} of 6 steps done.` : wf.message}
            </p>
            {wf.intent.budget_note && <p className="text-xs text-subtle">{wf.intent.budget_note}</p>}
            {wf.objective_id && wf.status !== "running" && (
              <Link href={`/objectives/${wf.objective_id}`} className="w-fit text-xs font-medium text-fg underline underline-offset-4">
                See the task plan
              </Link>
            )}
            <p className="text-xs text-subtle">
              Request read by {wf.intent.understood_by === "nemotron" ? "Nemotron, checked by PersonalIQ's rules" : "PersonalIQ's built-in rules"}.
            </p>
          </div>
        </div>
        <StatusPill status={wf.status} />
      </div>

      {["approved", "paid", "reconciliation_required"].includes(wf.status) && wf.result.approval_id && (
        <div className="pl-8">
          <Link href={`/approvals/${wf.result.approval_id}`} className="text-[13px] font-medium text-fg underline underline-offset-4">
            {wf.status === "paid" ? "View the paid order" : "View the approved order"}
          </Link>
          {wf.status === "paid" && wf.result.order_id && (
            <Link href={`/purchases/${wf.result.order_id}`} className="ml-4 text-[13px] font-medium text-fg underline underline-offset-4">
              Decision receipt
            </Link>
          )}
        </div>
      )}
      {wf.status === "awaiting_approval" && cart && (
        <>
          <div className="flex flex-wrap gap-x-5 gap-y-2 pl-8">
            <Stat label="Items" value={String(cart.lines.length)} />
            <Stat label="Total" value={formatMoney(cart.total, cart.currency)} />
            {cart.budget_evaluation && <Stat label="Budget used" value={`${cart.budget_evaluation.used_pct}%`} />}
          </div>
          <div className="flex flex-wrap items-center gap-2 pl-8">
            {wf.result.approval_id && (
              <Link
                href={`/approvals/${wf.result.approval_id}`}
                className="press inline-flex h-8 items-center gap-1.5 rounded-control bg-positive px-3 text-[13px] font-medium text-positive-fg hover:brightness-110"
              >
                <SealCheck size={14} aria-hidden /> Review and approve
              </Link>
            )}
            <Button variant="secondary" onClick={() => setShowCart(true)}>
              <ShoppingCart size={14} aria-hidden /> View cart
            </Button>
            {!!wf.result.risk_counts?.needs_decision && (
              <span className="text-xs text-negative">{wf.result.risk_counts.needs_decision} item(s) need your decision</span>
            )}
          </div>
        </>
      )}
      {(wf.status === "needs_input" || wf.status === "blocked" || wf.status === "failed") && (
        <div className="pl-8">
          <Link href="/" className="text-[13px] font-medium text-fg underline underline-offset-4">
            {wf.status === "needs_input" ? "Answer on Home" : "Try a different request"}
          </Link>
        </div>
      )}

      {cart && (
        <Dialog open={showCart} onClose={() => setShowCart(false)} icon={<ShoppingCart size={16} />} title="Proposed cart" subtitle={`${cart.lines.length} items, ${formatMoney(cart.total, cart.currency)} with shipping`}>
          <ul className="divide-y divide-line overflow-hidden rounded-card border border-line text-[13px]">
            {cart.lines.map((l) => (
              <li key={l.product.id}>
                <button onClick={() => setProduct({ product: l.product, score: l.score, note: l.reason })} className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-surface">
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-medium text-fg">{l.product.name}</span>
                    <span className="truncate text-xs text-subtle">{needLabel(l.need)}</span>
                  </span>
                  <span className="tabular shrink-0 text-fg">{formatMoney(l.line_total, cart.currency)}</span>
                </button>
              </li>
            ))}
          </ul>
        </Dialog>
      )}
      <ProductDialog view={product} onClose={() => setProduct(null)} />
    </div>
  );
}

function Timeline({ wf }: { wf: Workflow }) {
  const [selected, setSelected] = useState<AgentRun | null>(null);
  const runs = Object.fromEntries(wf.runs.map((r) => [r.agent_name, r]));
  const recoveries = wf.runs.filter((r) => r.agent_name === "supervisor_recover");
  const steps = STEPS.filter((s) => s !== "supervisor_recover" || recoveries.length > 0);

  return (
    <Section title="Timeline" description="Each step is one agent. Life Operations and Buyer work at the same time." icon={<ListChecks size={14} />}>
      <ol className="flex flex-col">
        {steps.map((step, i) => {
          const last = i === steps.length - 1;
          const keys = Array.isArray(step) ? step : [step];
          return (
            <li key={keys.join("+")} className="relative flex gap-3 pb-3 last:pb-0">
              {!last && <span className="absolute left-[15px] top-9 bottom-0 w-px bg-line" aria-hidden />}
              <span className="z-[1] mt-2 grid size-8 shrink-0 place-items-center rounded-full border border-line bg-panel">
                <StepIcon run={keys.map((k) => runs[k]).find(Boolean)} pending={keys[0] === "post_purchase"} wfStatus={wf.status} />
              </span>
              <div className={cn("grid min-w-0 flex-1 gap-2", keys.length > 1 && "sm:grid-cols-2")}>
                {keys.map((k) => (
                  <StepCard key={k} agentKey={k} run={runs[k]} wf={wf} parallel={keys.length > 1} onOpen={() => runs[k] && setSelected(runs[k])} />
                ))}
              </div>
            </li>
          );
        })}
      </ol>
      <StepDialog run={selected} onClose={() => setSelected(null)} />
    </Section>
  );
}

function StepCard({ agentKey, run, wf, parallel, onOpen }: { agentKey: string; run?: AgentRun; wf: Workflow; parallel: boolean; onOpen: () => void }) {
  const meta = AGENTS[agentKey];
  const waitingForPayment = agentKey === "post_purchase" && !run;
  const recoveries = agentKey === "supervisor_recover" ? wf.runs.filter((r) => r.agent_name === "supervisor_recover") : [];
  const note = recoveries.length > 1
    ? recoveries.map((r, i) => `${i + 1}. ${r.explanation}`).join(" ")
    : waitingForPayment
    ? wf.status === "awaiting_approval"
      ? "Waits for your approval and a verified PayPal payment."
      : "Runs after payment."
    : run
      ? run.explanation || (run.status === "running" ? "Working..." : "")
      : wf.status === "running"
        ? "Waiting for earlier steps."
        : "Not needed for this request.";

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={!run}
      className={cn("flex min-w-0 flex-col gap-1 rounded-card border border-line px-3 py-2.5 text-left", run ? "hover:bg-surface" : "cursor-default opacity-70")}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-semibold text-fg">
          <span className="text-muted">{meta.icon}</span>
          {meta.name}
          {parallel && <span className="rounded-full border border-line px-1.5 text-[10px] font-medium text-subtle">parallel</span>}
        </span>
        {run?.duration_ms != null && <span className="tabular text-xs text-subtle">{run.duration_ms} ms</span>}
      </span>
      <span className="text-xs text-muted">{meta.role}</span>
      {note && <span className={cn("text-[13px] leading-relaxed", run?.status === "failed" ? "text-negative" : "text-fg")}>{note}</span>}
    </button>
  );
}

function StepIcon({ run, pending, wfStatus }: { run?: AgentRun; pending: boolean; wfStatus: string }) {
  if (pending) return <HourglassMedium size={16} className="text-subtle" aria-label="Waiting" />;
  if (!run) return wfStatus === "running" ? <CircleDashed size={16} className="text-subtle" aria-label="Waiting" /> : <MinusCircle size={16} className="text-subtle" aria-label="Not run" />;
  switch (run.status) {
    case "completed":
      return <CheckCircle size={16} weight="fill" className="text-positive" aria-label="Done" />;
    case "failed":
      return <XCircle size={16} weight="fill" className="text-negative" aria-label="Failed" />;
    case "needs_input":
      return <Question size={16} weight="fill" className="text-caution" aria-label="Needs input" />;
    case "skipped":
      return <MinusCircle size={16} className="text-subtle" aria-label="Skipped" />;
    default:
      return <HourglassMedium size={16} className="text-fg" aria-label="Working" />;
  }
}
