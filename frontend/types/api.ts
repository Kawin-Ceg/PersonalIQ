export type Health = {
  status: string;
  version: string;
  database: "ok" | "unreachable" | "not_configured";
  paypal_configured: boolean;
  llm_configured: boolean;
  llm_provider: string;
  llm_model: string;
  llm_error: string | null;
};

export type Merchant = {
  id: string;
  slug: string;
  name: string;
  return_window_days: number;
};

/** Money arrives as a string ("149.99"). Format it; never do arithmetic on it in the browser. */
export type Product = {
  id: string;
  sku: string;
  name: string;
  category: string;
  description: string;
  price: string;
  currency: string;
  quality_score: number;
  durability_score: number;
  rating: number;
  review_count: number;
  availability: string;
  warranty_months: number;
  attributes: { need?: string; materials?: string[] };
  merchant: Merchant;
  /** Catalog price before conversion into the user's currency. */
  base_price: string | null;
  base_currency: string | null;
};

export type Catalog = {
  items: Product[];
  total: number;
  categories: { category: string; count: number }[];
  is_demo: boolean;
};

// ---- Personal Intelligence ----

export type Level = "high" | "medium" | "low";
export type Dimension = "durability" | "quality" | "price" | "value";
export type Source = "user_stated" | "uploaded" | "feedback" | "observed" | "inferred" | "default";

export type Signal = { level: Level; source: Source; reason: string };

export type UserContext = {
  user_id: string;
  name: string;
  currency: string;
  onboarded: boolean;
  budgets: { name: string; period: string; limit_amount: string; currency: string }[];
  importance: Record<Dimension, Signal>;
  price_sensitivity: Signal;
  avoid_materials: string[];
  like_merchants: string[];
  avoid_merchants: string[];
  likes: string[];
  dislikes: string[];
  lessons: string[];
  recent_interest: string[];
  spending: {
    window_days: number;
    currency: string;
    total: string;
    monthly_average: string;
    transaction_count: number;
    by_category: { category: string; total: string; share_pct: number }[];
    top_merchants: string[];
  } | null;
  scoring_weights: Record<Dimension | "fit", number>;
  memory_count: number;
};

export type MemoryItem = {
  id: string;
  memory_type: string;
  content: string;
  source: Source;
  confidence: number;
  created_at: string;
  updated_at: string;
  meta: { key?: string; level?: Level; value?: string };
};

export type FeedbackItem = {
  id: string;
  item_name: string;
  rating: number;
  worked: string;
  didnt_work: string;
  reasons: Dimension[];
  aspects?: Partial<Record<Aspect, number>>;
  created_at: string;
  learning?: Learning | null; // only on the response to a new rating
};

/** What you can rate after using something. */
export type Aspect = "quality" | "durability" | "value";

/** What a rating changed: the same ranking, before and after. */
export type Learning = {
  category: string;
  need: string;
  changed: boolean;
  summary: string;
  memories: { content: string; source: string; confidence: number; memory_id: string }[];
  weights: { key: string; label: string; before: number; after: number }[];
  moves: {
    product_id: string;
    name: string;
    rated: boolean;
    before_rank: number | null;
    after_rank: number | null;
    before_score: number | null;
    after_score: number | null;
    excluded?: string[] | null;
  }[];
};

export type DemoUser = { id: string; name: string; email: string; currency: string; onboarded_at: string | null };

export type OnboardingInput = {
  priorities: Dimension[];
  price_sensitivity: Level;
  avoid_materials: string[];
  like_merchants: string[];
  avoid_merchants: string[];
  likes: string[];
  dislikes: string[];
  monthly_budget: string | null;
};

// ---- Ranking, budget, cart ----

export type ScoreKey = "quality" | "value" | "price" | "durability" | "fit";

export type ScoreComponent = { key: ScoreKey; value: number; weight: number; contribution: number; reason: string };

export type RankedProduct = { product: Product; score: number; rank: number; components: ScoreComponent[] };

export type RankingResponse = {
  weights: Record<ScoreKey, number>;
  ranked: RankedProduct[];
  excluded: { product: Product; reasons: string[] }[];
};

export type NeedOption = { need: string; category: string; count: number };

export type BudgetEvaluation = {
  budget_name: string;
  limit: string;
  committed: string;
  proposed: string;
  remaining_after: string;
  within_budget: boolean;
  used_pct: number;
  currency: string;
  explanation: string;
};

export type CartPlan = {
  feasible: boolean;
  message: string;
  lines: { need: string; product: Product; quantity: number; unit_price: string; line_total: string; score: number; reason: string }[];
  skipped: { need: string; reason: string }[];
  shipping: { merchant: string; subtotal: string; shipping: string; note: string }[];
  subtotal: string;
  shipping_total: string;
  tax: string;
  total: string;
  budget: string;
  remaining: string;
  currency: string;
  budget_evaluation: BudgetEvaluation | null;
  tax_note: string;
};

// ---- Workflows ----

export type WorkflowStatus =
  | "running" | "awaiting_approval" | "needs_input" | "blocked" | "failed" | "approved" | "rejected"
  | "paid" | "cancelled" | "expired" | "reconciliation_required";

// ---- Payments ----

export type OrderStatus =
  | "draft" | "awaiting_approval" | "approved" | "rejected" | "paypal_order_created" | "awaiting_buyer_checkout"
  | "capturing" | "paid" | "failed" | "cancelled" | "expired" | "reconciliation_required";

/** What PayPal charges, derived by the server from the approved order. */
export type Charge = { currency: string; item_total: string; shipping: string; tax: string; total: string; rate_note: string };

export type PaymentView = {
  order_status: OrderStatus;
  id: string | null;
  status: string | null;
  attempt?: number;
  amount?: string;
  currency?: string;
  paypal_order_id?: string | null;
  paypal_status?: string | null;
  capture_id?: string | null;
  capture_status?: string | null;
  verified?: boolean;
  verified_at?: string | null;
  message?: string;
  already_captured?: boolean;
};

export type PayPalConfig = { enabled: boolean; client_id: string | null; currency: string | null; mode: string; webhooks_configured: boolean };
export type AgentKey =
  | "supervisor_plan" | "life_operations" | "consumer_buyer" | "procurement" | "financial"
  | "supervisor_recover" | "supervisor_verify" | "post_purchase";

export type AgentRun = {
  id: string;
  agent_name: AgentKey;
  status: "running" | "completed" | "needs_input" | "failed" | "skipped";
  explanation: string;
  output: { result?: Record<string, unknown>; errors?: string[]; status?: string };
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
};

export type Workflow = {
  id: string;
  objective_id: string | null;
  status: WorkflowStatus;
  objective: string;
  message: string;
  intent: { message: string; objective: string; template: string | null; budget: string | null; currency: string; budget_note: string | null; deadline: string | null; understood_by?: "nemotron" | "rules" };
  plan: { agent: string; goal: string; depends_on: string[] }[];
  runs: AgentRun[];
  result: { order_id?: string; approval_id?: string; risk_counts?: Record<"needs_decision" | "review" | "auto", number>; cart?: CartPlan; financial?: { flags: { level: string; message: string }[] }; question?: string; reason?: string };
  created_at: string;
  updated_at: string;
};

export type WorkflowSummary = {
  id: string;
  objective_id: string | null;
  status: WorkflowStatus;
  objective: string;
  message: string;
  total: string | null;
  currency: string | null;
  created_at: string;
};

// ---- Approvals ----

export type RiskLevel = "needs_decision" | "review" | "auto";
export type RiskFactor = { factor: string; points: number; reason: string };

export type ApprovalItem = {
  id: string;
  product: Product;
  quantity: number;
  unit_price: string;
  line_total: string;
  reason: string;
  risk: { level: RiskLevel; score: number; factors: RiskFactor[]; need?: string; rank?: number; match_score?: number; required?: boolean };
  decision: "kept" | "swapped" | null;
  trail: { step: string; actor: string; detail: string; at?: string; factors?: RiskFactor[] }[];
  alternatives: { product: Product; score: number; rank: number; difference: string }[];
};

export type TimelineEvent = { at: string; kind: "start" | "agent" | "decision" | "user" | "system" | "success" | "danger"; title: string; detail: string; actor: string };

export type ApprovalView = {
  id: string;
  status: "pending" | "approved" | "rejected" | "expired" | "superseded" | "invalidated";
  order_hash: string;
  order_version: number;
  expires_at: string;
  created_at: string | null;
  objective: string;
  workflow_id: string | null;
  order: { id: string; status: string; version: number; currency: string; subtotal: string; shipping: string; tax: string; total: string; merchants: string[] };
  items: ApprovalItem[];
  risk: { factors: RiskFactor[]; counts: Record<RiskLevel, number>; over_budget: boolean };
  budget: { budget_name?: string; limit?: string; remaining_after?: string; used_pct?: number; explanation?: string; within_budget?: boolean };
  can_approve: boolean;
  blockers: string[];
  replaced_by: string | null;
  timeline: TimelineEvent[];
  payment_method: string;
  charge: Charge;
  payment: PaymentView;
};

export type ApprovalSummary = {
  id: string;
  objective: string;
  total: string;
  currency: string;
  items: number;
  counts: Record<RiskLevel, number>;
  needs_decision_left: number;
  expires_at: string;
};
