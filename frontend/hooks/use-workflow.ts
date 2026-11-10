"use client";

import { useEffect, useState } from "react";
import { API_URL, apiGet, getCurrentUserId } from "@/lib/api";
import type { Workflow } from "@/types/api";

const TERMINAL = new Set(["awaiting_approval", "needs_input", "blocked", "failed"]);

/**
 * Live workflow state. Streams Server-Sent Events while agents work; falls back to polling if the
 * stream can't be opened. Stops once the workflow reaches a final state.
 */
export function useWorkflow(id: string | null) {
  const [wf, setWf] = useState<Workflow | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!id) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setWf(null);
    setError(false);

    const poll = () =>
      apiGet<Workflow>(`/workflows/${id}`)
        .then((w) => {
          if (stopped) return;
          setWf(w);
          if (!TERMINAL.has(w.status)) timer = setTimeout(poll, 1500);
        })
        .catch(() => !stopped && setError(true));

    const uid = getCurrentUserId();
    const es = new EventSource(`${API_URL}/workflows/${id}/events${uid ? `?user=${uid}` : ""}`);
    es.addEventListener("update", (e) => !stopped && setWf(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("done", () => es.close());
    es.onerror = () => {
      es.close();
      if (!stopped) poll(); // stream unavailable: keep the page live by polling
    };

    return () => {
      stopped = true;
      es.close();
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  return { wf, error };
}
