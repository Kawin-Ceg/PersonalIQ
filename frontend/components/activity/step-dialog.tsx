"use client";

import { Dialog } from "@/components/ui/dialog";
import { formatMoney, needLabel } from "@/lib/format";
import type { AgentRun, CartPlan } from "@/types/api";
import { AGENTS } from "./agent-meta";

type R = Record<string, unknown>;

/** What one agent did, in plain language. Raw JSON is never shown to the user. */
export function StepDialog({ run, onClose }: { run: AgentRun | null; onClose: () => void }) {
  const meta = run ? AGENTS[run.agent_name] : null;
  const result = (run?.output?.result ?? {}) as R;
  return (
    <Dialog
      open={!!run}
      onClose={onClose}
      icon={meta?.icon}
      title={meta?.name ?? ""}
      subtitle={meta ? `${meta.role}${run?.duration_ms != null ? ` · took ${run.duration_ms} ms` : ""}` : undefined}
    >
      {run && (
        <div className="flex flex-col gap-4 text-[13px]">
          <p className="text-[14px] leading-relaxed text-fg">{run.explanation || "No details."}</p>
          {run.output?.errors && run.output.errors.length > 0 && (
            <p className="rounded-card border border-negative/40 bg-negative/5 px-3 py-2 text-negative">{run.output.errors[0]}</p>
          )}
          <Detail agent={run.agent_name} result={result} />
        </div>
      )}
    </Dialog>
  );
}

function Detail({ agent, result }: { agent: string; result: R }) {
  if (agent === "supervisor_plan" && result.plan) {
    const plan = result.plan as { agent: string; goal: string }[];
    return (
      <List title="Plan">
        {plan.map((p, i) => (
          <li key={p.agent} className="px-3 py-2">
            <span className="tabular mr-2 text-subtle">{i + 1}</span>
            <span className="text-fg">{AGENTS[p.agent]?.name ?? p.agent}</span>
            <span className="text-muted">: {p.goal}</span>
          </li>
        ))}
      </List>
    );
  }
  if (agent === "life_operations" && result.needs) {
    const needs = result.needs as { need: string; required: boolean }[];
    return (
      <List title="What you need">
        {needs.map((n) => (
          <li key={n.need} className="flex justify-between px-3 py-2">
            <span className="text-fg">{needLabel(n.need)}</span>
            <span className={n.required ? "font-medium text-fg" : "text-subtle"}>{n.required ? "Must have" : "Nice to have"}</span>
          </li>
        ))}
      </List>
    );
  }
  if (agent === "consumer_buyer" && result.candidates) {
    const candidates = result.candidates as Record<string, { name: string; score: number }[]>;
    const excluded = (result.excluded as { name: string; reasons: string[] }[]) ?? [];
    return (
      <>
        <List title="Top pick for each need">
          {Object.entries(candidates)
            .slice(0, 8)
            .map(([need, items]) => (
              <li key={need} className="flex justify-between gap-3 px-3 py-2">
                <span className="text-muted">{needLabel(need)}</span>
                <span className="truncate text-right text-fg">
                  {items[0]?.name} <span className="tabular text-subtle">{items[0]?.score.toFixed(1)}</span>
                </span>
              </li>
            ))}
        </List>
        {excluded.length > 0 && (
          <List title="Left out">
            {excluded.map((e) => (
              <li key={e.name} className="px-3 py-2">
                <span className="text-fg">{e.name}</span>
                <span className="text-negative">: {e.reasons[0]}</span>
              </li>
            ))}
          </List>
        )}
      </>
    );
  }
  if (agent === "procurement" && result.cart) {
    const cart = result.cart as CartPlan;
    return (
      <List title={`Cart, ${formatMoney(cart.total, cart.currency)}`}>
        {cart.lines.map((l) => (
          <li key={l.product.id} className="flex justify-between gap-3 px-3 py-2">
            <span className="truncate text-fg">{l.product.name}</span>
            <span className="tabular shrink-0 text-muted">{formatMoney(l.line_total, cart.currency)}</span>
          </li>
        ))}
      </List>
    );
  }
  if (agent === "financial" && result.flags) {
    const flags = result.flags as { level: string; message: string }[];
    return flags.length ? (
      <List title="Checks">
        {flags.map((f) => (
          <li key={f.message} className={`px-3 py-2 ${f.level === "block" ? "text-negative" : f.level === "warn" ? "text-caution" : "text-muted"}`}>
            {f.message}
          </li>
        ))}
      </List>
    ) : (
      <p className="text-positive">All budget checks passed.</p>
    );
  }
  return null;
}

function List({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-semibold text-fg">{title}</p>
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line">{children}</ul>
    </div>
  );
}
