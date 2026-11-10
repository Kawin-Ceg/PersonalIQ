"use client";

import { ArrowsCounterClockwise, ChartLineUp, CheckSquareOffset, ClipboardText, Compass, Package, ShoppingCart, Storefront } from "@phosphor-icons/react";

export const AGENTS: Record<string, { name: string; role: string; icon: React.ReactNode }> = {
  supervisor_plan: { name: "Supervisor", role: "Plans the work and sets the budget", icon: <Compass size={16} /> },
  life_operations: { name: "Life Operations", role: "Works out what you need", icon: <ClipboardText size={16} /> },
  consumer_buyer: { name: "Consumer Buyer", role: "Researches and ranks products", icon: <Storefront size={16} /> },
  procurement: { name: "Procurement", role: "Builds the best cart within budget", icon: <ShoppingCart size={16} /> },
  financial: { name: "Financial Autopilot", role: "Checks the cart against your budgets", icon: <ChartLineUp size={16} /> },
  supervisor_recover: { name: "Supervisor", role: "Changed course after a failed step", icon: <ArrowsCounterClockwise size={16} /> },
  supervisor_verify: { name: "Supervisor", role: "Verifies the outcome", icon: <CheckSquareOffset size={16} /> },
  post_purchase: { name: "Post-Purchase", role: "Records the purchase after payment", icon: <Package size={16} /> },
};

/** Timeline order. Life Operations and Buyer share a row because they run in parallel. */
export const STEPS: (string | [string, string])[] = [
  "supervisor_plan",
  ["life_operations", "consumer_buyer"],
  "procurement",
  "financial",
  "supervisor_recover", // only shown when the supervisor had to recover
  "supervisor_verify",
  "post_purchase",
];
