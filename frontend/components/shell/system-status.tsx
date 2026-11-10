"use client";

import { useEffect, useState } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { apiGet } from "@/lib/api";
import type { Health } from "@/types/api";

type Row = { label: string; state: "ok" | "warn" | "off"; detail: string };

const HINT: Record<string, string> = {
  API: "PersonalIQ's backend server.",
  Database: "Where your profile, orders and payments are stored.",
  "PayPal Sandbox": "Test payment keys. Needed for checkout.",
  LLM: "Nemotron, used to understand requests and explain choices. If it's unavailable, PersonalIQ still works with plain wording.",
};

function rows(health: Health | null, reachable: boolean): Row[] {
  if (!reachable || !health) {
    return [{ label: "API", state: "off", detail: "Not reachable" }];
  }
  return [
    { label: "API", state: "ok", detail: `v${health.version}` },
    {
      label: "Database",
      state: health.database === "ok" ? "ok" : health.database === "not_configured" ? "warn" : "off",
      detail: health.database === "ok" ? "Connected" : health.database === "not_configured" ? "Not set" : "Unreachable",
    },
    { label: "PayPal Sandbox", state: health.paypal_configured ? "ok" : "warn", detail: health.paypal_configured ? "Ready" : "No keys" },
    {
      label: "LLM",
      state: !health.llm_configured ? "warn" : health.llm_error ? "off" : "ok",
      detail: !health.llm_configured ? "No key" : (health.llm_error ?? health.llm_provider),
    },
  ];
}

const DOT: Record<Row["state"], string> = {
  ok: "bg-positive",
  warn: "bg-caution",
  off: "bg-negative",
};

export function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = () =>
      apiGet<Health>("/health")
        .then((h) => alive && (setHealth(h), setReachable(true)))
        .catch(() => alive && setReachable(false));
    load();
    const id = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex flex-col gap-2 text-xs">
      <p className="font-medium text-subtle">Status</p>
      <ul className="flex flex-col gap-1.5">
        {rows(health, reachable).map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-3">
            <Tooltip label={HINT[r.label]} side="right">
              <span tabIndex={0} className="flex cursor-help items-center gap-2 text-muted">
                <span className={`size-1.5 rounded-full ${DOT[r.state]}`} aria-hidden />
                {r.label}
              </span>
            </Tooltip>
            <span className="text-subtle">{r.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
