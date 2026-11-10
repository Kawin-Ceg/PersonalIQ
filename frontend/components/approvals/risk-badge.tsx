import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import type { RiskLevel } from "@/types/api";

export const RISK: Record<RiskLevel, { label: string; cls: string; hint: string }> = {
  needs_decision: {
    label: "Needs your decision",
    cls: "border-negative/40 bg-negative/10 text-negative",
    hint: "Risky enough that you must keep, swap or remove it before approving.",
  },
  review: { label: "Worth a look", cls: "border-caution/40 bg-caution/10 text-caution", hint: "Some risk. No action needed, but have a look." },
  auto: { label: "Confident", cls: "border-positive/40 bg-positive/10 text-positive", hint: "Low risk: a strong match at a sensible price." },
};

export function RiskBadge({ level, score }: { level: RiskLevel; score?: number }) {
  const r = RISK[level];
  return (
    <Tooltip label={`${r.hint}${score !== undefined ? ` Risk ${score}/100.` : ""}`}>
      <span tabIndex={0} className={cn("inline-flex h-6 shrink-0 cursor-help items-center gap-1 rounded-full border px-2 text-xs font-semibold", r.cls)}>
        {r.label}
        {score !== undefined && <span className="tabular font-normal opacity-80">{score}</span>}
      </span>
    </Tooltip>
  );
}
