import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import type { ReceiptState } from "@/types/receipt";

export const RECEIPT_STATE: Record<ReceiptState, { label: string; cls: string; hint: string }> = {
  proposed: { label: "Proposed", cls: "border-line-strong text-muted", hint: "Waiting for your approval. Nothing is bought yet." },
  approved: { label: "Approved", cls: "border-line-strong text-fg", hint: "You approved this exact order. Not paid yet." },
  payment_pending: { label: "Payment pending", cls: "border-caution/40 bg-caution/10 text-caution", hint: "Checkout is open or PayPal hasn't confirmed the capture yet." },
  paid: { label: "Paid", cls: "border-positive/40 bg-positive/10 text-positive", hint: "PayPal confirmed the capture for the approved amount." },
  payment_failed: { label: "Payment failed", cls: "border-negative/40 bg-negative/10 text-negative", hint: "PayPal didn't complete the payment. Nothing was charged." },
  not_bought: { label: "Not bought", cls: "border-line-strong text-muted", hint: "Rejected, cancelled or expired before payment." },
};

export function ReceiptStateBadge({ state, large = false }: { state: ReceiptState; large?: boolean }) {
  const s = RECEIPT_STATE[state];
  return (
    <Tooltip label={s.hint}>
      <span tabIndex={0} className={cn("inline-flex shrink-0 cursor-help items-center rounded-full border font-semibold", large ? "h-7 px-3 text-[13px]" : "h-6 px-2.5 text-xs", s.cls)}>
        {s.label}
      </span>
    </Tooltip>
  );
}
