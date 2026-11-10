"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  CalendarBlank,
  CheckCircle,
  Circle,
  HourglassMedium,
  Lightning,
  ListChecks,
  Robot,
  ShoppingBag,
  Signpost,
  User,
  WarningCircle,
} from "@phosphor-icons/react";
import { AGENTS } from "@/components/activity/agent-meta";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import type { ObjectiveTask, ObjectiveView as ObjectiveData } from "@/types/objective";

const PHASES: { title: string; description: string; icon: React.ReactNode; keys: string[] }[] = [
  { title: "Before you buy", description: "Things only you can arrange. PersonalIQ keeps them on the list.", icon: <Signpost size={14} />, keys: ["address", "movers", "utilities"] },
  { title: "Buying", description: "Done by the agents, with your approval and payment in the middle.", icon: <ShoppingBag size={14} />, keys: ["needs", "research", "cart", "budget", "approve", "pay"] },
  { title: "After you buy", description: "Deliveries, returns and how things worked out.", icon: <CheckCircle size={14} />, keys: ["deliveries", "returns", "feedback", "notify"] },
];

const shortDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

function ownerName(owner: string) {
  return owner === "you" ? "You" : AGENTS[owner]?.name ?? owner;
}

function detailOf(e: unknown) {
  return e instanceof ApiError ? e.message.replace(/^"|"$/g, "") : "Something went wrong.";
}

export function ObjectiveView({ id }: { id: string }) {
  const [o, setO] = useState<ObjectiveData | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<ObjectiveTask | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiGet<ObjectiveData>(`/objectives/${id}`).then(setO).catch(() => setFailed(true));
  }, [id]);
  useEffect(load, [load]);

  async function toggle(t: ObjectiveTask) {
    setBusy(true);
    setError(null);
    try {
      const next = await apiPost<ObjectiveData>(`/objectives/${id}/tasks/${t.id}`, { done: t.state !== "done" });
      setO(next);
      setSelected(null);
    } catch (e) {
      setError(detailOf(e));
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <p className="text-[13px] text-negative">Couldn&apos;t load this objective. Check that the API is running.</p>;
  if (!o) return <div className="skeleton h-64 w-full max-w-[860px]" aria-busy="true" aria-label="Loading" />;

  const keyed = Object.fromEntries(o.tasks.map((t) => [t.key, t]));
  const phases = PHASES.map((p) => ({ ...p, tasks: p.keys.map((k) => keyed[k]).filter(Boolean) })).filter((p) => p.tasks.length);
  const placed = new Set(PHASES.flatMap((p) => p.keys));
  const other = o.tasks.filter((t) => !placed.has(t.key));
  const overdue = o.tasks.filter((t) => t.overdue).length;

  return (
    <div className="flex max-w-[860px] flex-col gap-8 pb-16">
      <PageHeader
        icon={<ListChecks size={18} />}
        title={o.title}
        description="The plan Life Operations made for this objective. Agent tasks tick themselves from real events; yours you tick when they're done."
      />

      <section className="flex flex-col gap-4 rounded-card border border-line p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-subtle">Progress</span>
            <span className="tabular text-3xl font-semibold tracking-tight text-fg">
              {o.progress.done} <span className="text-lg font-medium text-subtle">of {o.progress.total} tasks</span>
            </span>
          </div>
          <div className="flex flex-col items-end gap-1 text-xs text-subtle">
            {o.deadline ? (
              <span className="inline-flex items-center gap-1">
                <CalendarBlank size={12} aria-hidden /> Target {shortDate(o.deadline)}
              </span>
            ) : (
              <span>No target date, so tasks have no due dates</span>
            )}
            {overdue > 0 && <span className="font-medium text-negative">{overdue} overdue</span>}
          </div>
        </div>
        <span className="flex h-2 w-full overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={o.progress.pct} aria-valuemin={0} aria-valuemax={100} aria-label="Tasks done">
          <span className="h-full rounded-full bg-positive" style={{ width: `${o.progress.pct}%` }} />
        </span>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-3">
          {o.budget_limit && <Stat label="Budget" value={formatMoney(o.budget_limit, o.currency)} />}
          {o.links.workflow_id && (
            <Link href={`/activity?w=${o.links.workflow_id}`} className="text-[13px] font-medium text-fg underline underline-offset-4">
              How the agents worked
            </Link>
          )}
          {o.links.order_status === "paid" && o.links.order_id ? (
            <Link href={`/purchases/${o.links.order_id}`} className="text-[13px] font-medium text-fg underline underline-offset-4">
              Decision receipt
            </Link>
          ) : (
            o.links.approval_id && (
              <Link href={`/approvals/${o.links.approval_id}`} className="text-[13px] font-medium text-fg underline underline-offset-4">
                The order
              </Link>
            )
          )}
        </div>
        {o.warnings.map((w) => (
          <p key={w} className={cn("flex items-start gap-2 text-[13px]", w.startsWith("Tight") ? "text-caution" : "text-muted")}>
            <WarningCircle size={14} className="mt-0.5 shrink-0" aria-hidden /> {w}
          </p>
        ))}
      </section>

      {o.next.length > 0 && (
        <Section title="Up next" description="Ready to do now, soonest due first." icon={<Lightning size={14} />}>
          <TaskList tasks={o.next} onOpen={setSelected} onToggle={toggle} busy={busy} />
        </Section>
      )}

      {phases.map((p) => (
        <Section key={p.title} title={`${p.title} (${p.tasks.filter((t) => t.state === "done").length}/${p.tasks.length})`} description={p.description} icon={p.icon}>
          <TaskList tasks={p.tasks} onOpen={setSelected} onToggle={toggle} busy={busy} />
        </Section>
      ))}
      {other.length > 0 && (
        <Section title="Other" icon={<ListChecks size={14} />}>
          <TaskList tasks={other} onOpen={setSelected} onToggle={toggle} busy={busy} />
        </Section>
      )}

      {error && !selected && <p className="text-[13px] text-negative">{error}</p>}

      {selected && (
        <Dialog
          open
          onClose={() => {
            setSelected(null);
            setError(null);
          }}
          icon={selected.owner === "you" ? <User size={16} /> : AGENTS[selected.owner]?.icon ?? <Robot size={16} />}
          title={selected.title}
          subtitle={`${ownerName(selected.owner)} · ${selected.tracking === "auto" ? "ticked automatically" : "you tick it"}`}
          footer={
            selected.tracking === "manual" ? (
              <Button variant={selected.state === "done" ? "ghost" : "positive"} disabled={busy || (selected.state === "waiting")} onClick={() => toggle(selected)}>
                {selected.state === "done" ? "Mark as not done" : "Mark done"}
              </Button>
            ) : undefined
          }
        >
          <dl className="flex flex-col gap-3 text-[13px]">
            <Row label="What it is">{selected.detail || "No details."}</Row>
            <Row label="Status">
              {selected.state === "done"
                ? `Done${selected.completed_at ? `, ${shortDate(selected.completed_at)}` : ""}`
                : selected.state === "ready"
                  ? "Ready to do"
                  : `Waiting on: ${selected.waiting_on.join(", ")}`}
            </Row>
            {selected.due_on && (
              <Row label="Due">
                <span className={cn(selected.overdue && "font-medium text-negative")}>
                  {shortDate(selected.due_on)}
                  {selected.overdue && " (overdue)"}
                </span>
              </Row>
            )}
            {selected.depends_on.length > 0 && <Row label="Comes after">{selected.depends_on.join(", ")}</Row>}
            <Row label="How it's ticked">
              {selected.tracking === "auto"
                ? "Automatically, from what actually happens: the agents finishing, your approval, PayPal confirming the payment, or every item being rated. It can't be ticked by hand."
                : "By you, when it's done."}
            </Row>
            {error && <p className="text-negative">{error}</p>}
          </dl>
        </Dialog>
      )}
    </div>
  );
}

function TaskList({ tasks, onOpen, onToggle, busy }: { tasks: ObjectiveTask[]; onOpen: (t: ObjectiveTask) => void; onToggle: (t: ObjectiveTask) => void; busy: boolean }) {
  return (
    <ul className="overflow-hidden rounded-card border border-line">
      {tasks.map((t) => (
        <li key={t.id} className="flex items-center gap-1 border-b border-line pr-3 last:border-b-0">
          <button onClick={() => onOpen(t)} className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 text-left hover:bg-surface">
            <StateIcon t={t} />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className={cn("truncate text-[13px] font-medium", t.state === "done" ? "text-muted line-through decoration-line-strong" : "text-fg")}>{t.title}</span>
              <span className="truncate text-xs text-subtle">
                {ownerName(t.owner)}
                {t.external && " · outside PersonalIQ"}
                {t.due_on && (
                  <span className={cn(t.overdue && "font-medium text-negative")}>
                    {" "}
                    · due {shortDate(t.due_on)}
                    {t.overdue && " (overdue)"}
                  </span>
                )}
                {t.state === "waiting" && ` · after ${t.waiting_on[0]}${t.waiting_on.length > 1 ? ` +${t.waiting_on.length - 1}` : ""}`}
              </span>
            </span>
          </button>
          {t.tracking === "manual" ? (
            <Tooltip label={t.state === "waiting" ? `Waits on ${t.waiting_on.join(", ")}` : t.state === "done" ? "Mark as not done" : "Mark done"}>
              <button
                type="button"
                disabled={busy || t.state === "waiting"}
                onClick={() => onToggle(t)}
                aria-label={t.state === "done" ? `Mark ${t.title} as not done` : `Mark ${t.title} done`}
                className={cn(
                  "grid size-7 shrink-0 place-items-center rounded-control border disabled:opacity-40",
                  t.state === "done" ? "border-positive/40 bg-positive/10 text-positive" : "border-line text-subtle hover:border-positive/40 hover:text-positive",
                )}
              >
                <CheckCircle size={16} weight={t.state === "done" ? "fill" : "regular"} aria-hidden />
              </button>
            </Tooltip>
          ) : (
            <Tooltip label="Ticked automatically from real events">
              <span tabIndex={0} className="inline-flex h-6 shrink-0 cursor-help items-center gap-1 rounded-full border border-line px-2 text-[11px] text-subtle">
                <Robot size={12} aria-hidden /> Auto
              </span>
            </Tooltip>
          )}
        </li>
      ))}
    </ul>
  );
}

function StateIcon({ t }: { t: ObjectiveTask }) {
  if (t.state === "done") return <CheckCircle size={18} weight="fill" className="shrink-0 text-positive" aria-label="Done" />;
  if (t.state === "waiting") return <HourglassMedium size={18} className="shrink-0 text-subtle" aria-label="Waiting" />;
  return t.overdue ? (
    <WarningCircle size={18} weight="fill" className="shrink-0 text-negative" aria-label="Overdue" />
  ) : (
    <span className="relative shrink-0" aria-label="Ready">
      <Circle size={18} className="text-fg" aria-hidden />
      <ArrowRight size={9} weight="bold" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-fg" aria-hidden />
    </span>
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
