import type { Charge, OrderStatus, PaymentView } from "./api";

/** What a receipt may claim. "paid" only after a verified PayPal capture. */
export type ReceiptState = "proposed" | "approved" | "payment_pending" | "paid" | "payment_failed" | "not_bought";

export type ReceiptItem = {
  id: string;
  product_id: string;
  name: string;
  category: string;
  need: string;
  merchant: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  reason: string;
  score: number | null;
  rank: number | null;
  risk_level: string | null;
  risk_score: number | null;
  your_decision: "kept" | "swapped" | null;
  alternatives: { name: string; score: number; rank: number; why_not: string }[];
};

export type FollowUp = {
  item_id: string;
  product_id: string;
  name: string;
  category: string;
  merchant: string;
  return_by: string;
  return_window_days: number;
  warranty_until: string | null;
  warranty_months: number;
  feedback_after: string;
  feedback: { rating: number; aspects?: Record<string, number>; worked: string; didnt_work: string; at: string | null } | null;
  delivery: null;
};

export type Receipt = {
  order_id: string;
  state: ReceiptState;
  order_status: OrderStatus;
  version: number;
  request: { message: string; objective: string; understood_by: string | null; at: string | null };
  agents: { agent: string; name: string; title: string; status: string; explanation: string; duration_ms: number | null }[];
  research: {
    ranked_needs: number;
    candidates_considered: number;
    excluded: { product_id: string; name: string; reasons: string[] }[];
    weights: Record<string, number>;
    skipped_needs: { need: string; reason: string }[];
  };
  items: ReceiptItem[];
  financial: { explanation: string; budget_name?: string | null; limit?: string | null; remaining_after?: string | null; used_pct?: number | null; within_budget?: boolean | null };
  approval: { approved: boolean; approved_at: string | null; version: number | null; fingerprint: string | null };
  totals: { currency: string; subtotal: string; shipping: string; tax: string; total: string; charge: Charge };
  payment: PaymentView;
  completed_at: string | null;
  follow_up: { items: FollowUp[]; delivery_note: string };
  notes: string[];
};

export type OrderSummary = {
  order_id: string;
  state: ReceiptState;
  order_status: OrderStatus;
  objective: string;
  total: string;
  currency: string;
  items: number;
  charged: { amount: string; currency: string } | null;
  paid_at: string | null;
  updated_at: string | null;
  feedback_left: number;
};
