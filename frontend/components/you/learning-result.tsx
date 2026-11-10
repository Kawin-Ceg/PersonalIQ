import { ArrowDown, ArrowRight, ArrowUp, Brain, ListNumbers, Scales } from "@phosphor-icons/react";
import { cn } from "@/lib/cn";
import type { Learning } from "@/types/api";

const pct = (w: number) => `${Math.round(w * 100)}%`;

/** Shown right after a rating: what PersonalIQ learned and how the ranking moved because of it. */
export function LearningResult({ learning }: { learning: Learning }) {
  const changedWeights = learning.weights.filter((w) => w.before !== w.after);
  return (
    <div className="flex flex-col gap-5 text-[13px]">
      <p className="rounded-card border border-line bg-surface px-4 py-3 text-[14px] leading-relaxed text-fg">{learning.summary}</p>

      {learning.memories.length > 0 && (
        <Block icon={<Brain size={14} />} title="What it learned">
          <ul className="flex flex-col gap-2">
            {learning.memories.map((m) => (
              <li key={m.memory_id} className="flex flex-col gap-0.5 rounded-control border border-line px-3 py-2">
                <span className="text-fg">{m.content}</span>
                <span className="text-xs text-subtle">
                  Learned from your rating, {Math.round(m.confidence * 100)}% confidence. You can change or delete it under You.
                </span>
              </li>
            ))}
          </ul>
        </Block>
      )}

      {changedWeights.length > 0 && (
        <Block icon={<Scales size={14} />} title={`How a ${learning.category} pick is scored now`}>
          <ul className="flex flex-col gap-1.5">
            {learning.weights.map((w) => {
              const delta = w.after - w.before;
              return (
                <li key={w.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                  <span className="flex flex-col gap-1">
                    <span className={cn("text-xs", delta !== 0 ? "font-medium text-fg" : "text-subtle")}>{w.label}</span>
                    <span className="relative h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                      <span className="absolute inset-y-0 left-0 rounded-full bg-line-strong" style={{ width: pct(w.before) }} />
                      <span className={cn("absolute inset-y-0 left-0 rounded-full", delta !== 0 ? "bg-fg" : "bg-line-strong")} style={{ width: pct(w.after) }} />
                    </span>
                  </span>
                  <span className="tabular inline-flex w-24 items-center justify-end gap-1 text-xs">
                    <span className="text-subtle">{pct(w.before)}</span>
                    <ArrowRight size={10} className="text-subtle" aria-hidden />
                    <span className={cn(delta !== 0 ? "font-semibold text-fg" : "text-subtle")}>{pct(w.after)}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </Block>
      )}

      {learning.moves.length > 0 && (
        <Block icon={<ListNumbers size={14} />} title={`Ranking for ${learning.need.replace(/_/g, " ")}`}>
          <ul className="overflow-hidden rounded-control border border-line">
            {learning.moves.map((m) => {
              const up = m.after_rank != null && m.before_rank != null && m.after_rank < m.before_rank;
              const down = m.after_rank != null && m.before_rank != null && m.after_rank > m.before_rank;
              return (
                <li key={m.product_id} className="flex items-center gap-3 border-b border-line px-3 py-2 last:border-b-0">
                  <span className="min-w-0 flex-1 truncate text-fg">
                    {m.name}
                    {m.rated && <span className="text-subtle"> (yours)</span>}
                  </span>
                  {m.excluded ? (
                    <span className="text-xs font-medium text-negative">Won&apos;t be suggested</span>
                  ) : (
                    <span className="tabular inline-flex items-center gap-1 text-xs">
                      <span className="text-subtle">#{m.before_rank ?? "–"}</span>
                      <ArrowRight size={10} className="text-subtle" aria-hidden />
                      <span className="font-semibold text-fg">#{m.after_rank}</span>
                      {up && <ArrowUp size={12} className="text-positive" aria-label="moved up" />}
                      {down && <ArrowDown size={12} className="text-negative" aria-label="moved down" />}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Block>
      )}
    </div>
  );
}

function Block({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="flex items-center gap-1.5 text-xs font-medium text-subtle">
        <span aria-hidden>{icon}</span>
        {title}
      </span>
      {children}
    </div>
  );
}
