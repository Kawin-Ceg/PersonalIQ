export type TaskState = "done" | "ready" | "waiting";

export type ObjectiveTask = {
  id: string;
  key: string;
  title: string;
  detail: string;
  owner: string; // "you" or an agent key
  tracking: "auto" | "manual";
  external: boolean;
  depends_on: string[];
  waiting_on: string[];
  due_on: string | null;
  state: TaskState;
  overdue: boolean;
  completed_at: string | null;
};

export type ObjectiveView = {
  id: string;
  title: string;
  description: string;
  status: string;
  deadline: string | null;
  budget_limit: string | null;
  currency: string;
  created_at: string | null;
  progress: { done: number; total: number; pct: number };
  next: ObjectiveTask[];
  tasks: ObjectiveTask[];
  warnings: string[];
  links: { workflow_id: string | null; order_id: string | null; order_status: string | null; approval_id: string | null };
};
