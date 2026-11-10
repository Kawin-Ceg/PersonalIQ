import { cn } from "@/lib/cn";
import type { WorkflowStatus } from "@/types/api";

const STYLE: Record<WorkflowStatus, { label: string; cls: string; hint: string }> = {
  running: { label: "Working", cls: "border-line-strong text-fg", hint: "Agents are working on it." },
  awaiting_approval: { label: "Ready for approval", cls: "border-positive/40 bg-positive/10 text-positive", hint: "A cart is ready. Nothing is bought until you approve." },
  needs_input: { label: "Needs your input", cls: "border-caution/40 bg-caution/10 text-caution", hint: "PersonalIQ has a question before it can continue." },
  blocked: { label: "Blocked", cls: "border-negative/40 bg-negative/10 text-negative", hint: "This can't be done as asked. The reason is shown." },
  failed: { label: "Failed", cls: "border-negative/40 bg-negative/10 text-negative", hint: "Something went wrong. Try again." },
  approved: { label: "Approved", cls: "border-positive/40 bg-positive/10 text-positive", hint: "You approved the exact order. Payment comes next." },
  rejected: { label: "Rejected", cls: "border-line-strong text-muted", hint: "You rejected this order. Nothing was bought." },
  paid: { label: "Paid", cls: "border-positive/40 bg-positive/10 text-positive", hint: "PayPal confirmed the payment." },
  cancelled: { label: "Cancelled", cls: "border-line-strong text-muted", hint: "Cancelled before payment. Nothing was charged." },
  expired: { label: "Expired", cls: "border-negative/40 bg-negative/10 text-negative", hint: "The approval ran out before payment." },
  reconciliation_required: { label: "Checking payment", cls: "border-caution/40 bg-caution/10 text-caution", hint: "The payment outcome is being confirmed with PayPal." },
};

export function StatusPill({ status }: { status: WorkflowStatus }) {
  const s = STYLE[status] ?? STYLE.running;
  return (
    <span title={s.hint} className={cn("inline-flex h-6 shrink-0 items-center rounded-full border px-2.5 text-xs font-semibold", s.cls)}>
      {s.label}
    </span>
  );
}
