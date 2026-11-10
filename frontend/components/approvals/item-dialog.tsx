"use client";

import { ArrowsLeftRight, Check, MinusCircle, PlusCircle, Trash } from "@phosphor-icons/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { CategoryIcon } from "@/components/ui/category-icon";
import { Dialog } from "@/components/ui/dialog";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";
import type { ApprovalItem } from "@/types/api";
import { RiskBadge } from "./risk-badge";

/** One item: why it's here (decision trail), what makes it risky, and what you can do about it. */
export function ItemDialog({
  item,
  currency,
  editable,
  busy,
  onClose,
  onAction,
}: {
  item: ApprovalItem | null;
  currency: string;
  editable: boolean;
  busy: boolean;
  onClose: () => void;
  onAction: (action: "keep" | "remove" | "swap", productId?: string) => void;
}) {
  const [confirmRemove, setConfirmRemove] = useState(false);
  const p = item?.product;

  return (
    <Dialog
      open={!!item}
      onClose={() => {
        setConfirmRemove(false);
        onClose();
      }}
      wide
      icon={p ? <CategoryIcon category={p.category} size={16} /> : null}
      title={p?.name ?? ""}
      subtitle={p ? `${needLabel(p.attributes.need ?? "general")} · ${p.merchant.name} · ${formatMoney(item!.line_total, currency)}` : undefined}
      footer={
        item && editable ? (
          confirmRemove ? (
            <>
              <span className="mr-auto self-center text-[13px] text-muted">Remove it from the order? You&apos;ll review the new total.</span>
              <Button variant="ghost" onClick={() => setConfirmRemove(false)}>
                Keep it
              </Button>
              <Button variant="danger" disabled={busy} onClick={() => onAction("remove")}>
                <Trash size={14} aria-hidden /> Yes, remove
              </Button>
            </>
          ) : (
            <>
              <Button variant="danger" className="mr-auto" disabled={busy} onClick={() => setConfirmRemove(true)}>
                <Trash size={14} aria-hidden /> Remove
              </Button>
              <Button variant="positive" disabled={busy || item.decision !== null} onClick={() => onAction("keep")}>
                <Check size={14} aria-hidden /> {item.decision ? "Decided" : "Keep this"}
              </Button>
            </>
          )
        ) : undefined
      }
    >
      {item && (
        <div className="flex flex-col gap-6 text-[13px]">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={item.risk.level} score={item.risk.score} />
            {item.decision && (
              <span className="inline-flex h-6 items-center gap-1 rounded-full border border-positive/40 px-2 text-xs font-semibold text-positive">
                <Check size={12} aria-hidden /> You {item.decision} this
              </span>
            )}
          </div>

          {/* Decision trail */}
          <section className="flex flex-col gap-2">
            <p className="font-semibold text-fg">How this item got here</p>
            <ol className="flex flex-col">
              {item.trail.map((t, i) => (
                <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < item.trail.length - 1 && <span className="absolute bottom-0 left-[11px] top-6 w-px bg-line" aria-hidden />}
                  <span className="tabular z-[1] grid size-6 shrink-0 place-items-center rounded-full border border-line bg-panel text-[11px] text-muted">{i + 1}</span>
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="font-medium text-fg">
                      {t.step} <span className="font-normal text-subtle">by {t.actor}</span>
                    </p>
                    {t.detail && <p className="leading-relaxed text-muted">{t.detail}</p>}
                    {t.factors && t.factors.length > 0 && (
                      <ul className="mt-1 flex flex-col gap-1">
                        {t.factors.map((f) => (
                          <li key={f.factor} className="flex items-start gap-2">
                            {f.points >= 0 ? (
                              <PlusCircle size={14} className="mt-0.5 shrink-0 text-negative" aria-hidden />
                            ) : (
                              <MinusCircle size={14} className="mt-0.5 shrink-0 text-positive" aria-hidden />
                            )}
                            <span className={cn("tabular w-9 shrink-0 font-medium", f.points >= 0 ? "text-negative" : "text-positive")}>
                              {f.points > 0 ? `+${f.points}` : f.points}
                            </span>
                            <span className="text-muted">{f.reason}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {t.factors && t.factors.length === 0 && <p className="text-positive">No risk factors.</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* Alternatives */}
          {editable && item.alternatives.length > 0 && (
            <section className="flex flex-col gap-2">
              <p className="font-semibold text-fg">Swap for an alternative</p>
              <ul className="divide-y divide-line overflow-hidden rounded-card border border-line">
                {item.alternatives.map((a) => {
                  const more = !a.difference.startsWith("-");
                  return (
                    <li key={a.product.id} className="flex items-center gap-3 px-3 py-2.5">
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate font-medium text-fg">{a.product.name}</span>
                        <span className="text-xs text-subtle">
                          #{a.rank} for you, match score {a.score.toFixed(1)} · {a.product.merchant.name}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end">
                        <span className="tabular font-medium text-fg">{formatMoney(a.product.price, currency)}</span>
                        <span className={cn("tabular text-xs", more ? "text-negative" : "text-positive")}>
                          {more ? "+" : "-"}
                          {formatMoney(a.difference.replace("-", ""), currency)}
                        </span>
                      </span>
                      <Button variant="secondary" disabled={busy} onClick={() => onAction("swap", a.product.id)}>
                        <ArrowsLeftRight size={14} aria-hidden /> Swap
                      </Button>
                    </li>
                  );
                })}
              </ul>
              <p className="text-xs text-subtle">Swapping or removing creates a new version of the order. Your earlier approval progress for other items is kept.</p>
            </section>
          )}
        </div>
      )}
    </Dialog>
  );
}
