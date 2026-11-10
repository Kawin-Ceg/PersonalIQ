export type FinanceBudget = {
  name: string;
  period: "monthly" | "one_off" | string;
  currency: string;
  period_label: string;
  limit: string;
  spent: string;
  in_flight: string;
  left: string;
  used_pct: number;
  over: boolean;
};

export type FinanceOverview = {
  currency: string;
  as_of: string;
  window_days: number;
  has_data: boolean;
  transaction_count: number;
  sources: { uploaded: number; paypal: number };
  months: { month: string; label: string; partial: boolean; total: string; everyday: string; planned: string }[];
  everyday_monthly_average: string | null;
  planned_total: string;
  categories: { category: string; total: string; share_pct: number; count: number; last_30: string; prior_30: string; change_pct: number | null }[];
  recurring: { merchant: string; category: string; cadence: string; amount: string; monthly_cost: string; times_seen: number; last_paid: string; next_expected: string }[];
  recurring_monthly_total: string;
  unusual: { on: string; merchant: string; category: string; amount: string; usual: string; times_usual: string }[];
  forecast: {
    month: string;
    so_far: string;
    days_left: number;
    recurring_still_due: string;
    recurring_due: string[];
    daily_variable_rate: string;
    projected_total: string;
    assumptions: string[];
  };
  budgets: FinanceBudget[];
};

export type Affordability = {
  amount: string;
  currency: string;
  verdict: "fits" | "tight" | "over" | "unknown";
  budget: string | null;
  left_after: string | null;
  used_pct_after: number | null;
  lines: string[];
};
