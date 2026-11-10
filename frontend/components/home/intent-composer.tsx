"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowCounterClockwise, ArrowUp, Sparkle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";

// No amounts here: PersonalIQ uses your saved budget, in your own currency. Add an amount to override it.
const SUGGESTIONS = ["Set up my new apartment with the essentials", "Find a durable office chair", "Kitchen basics for one person"];

type Understood = {
  objective: string;
  template: string | null;
  needs: { need: string; required: boolean }[];
  budget: string | null;
  currency: string;
  budget_note: string | null;
  deadline: string | null;
  understood_by: "nemotron" | "rules";
};

type ChatOut = {
  conversation_id: string;
  reply: string;
  status: "clarifying" | "started";
  workflow_id: string | null;
  suggestions: string[];
  understood: Understood;
};

type Turn = { role: "user" | "assistant"; text: string; suggestions?: string[]; understood?: Understood };

export function IntentComposer() {
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const answering = conversationId !== null;

  async function send(message: string) {
    const msg = message.trim();
    if (!msg || busy) return;
    setBusy(true);
    setError(null);
    setTurns((t) => [...t, { role: "user", text: msg }]);
    setText("");
    try {
      const res = await apiPost<ChatOut>("/chat", { conversation_id: conversationId, message: msg });
      if (res.status === "started" && res.workflow_id) {
        router.push(`/activity?w=${res.workflow_id}`); // watch the agents work
        return;
      }
      setConversationId(res.conversation_id);
      setTurns((t) => [...t, { role: "assistant", text: res.reply, suggestions: res.suggestions, understood: res.understood }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't reach PersonalIQ. Is the API running?");
      setTurns((t) => t.slice(0, -1));
      setText(msg);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setTurns([]);
    setConversationId(null);
    setError(null);
    setText("");
  }

  const lastAssistant = [...turns].reverse().find((t) => t.role === "assistant");

  return (
    <div className="flex flex-col gap-4">
      {turns.length > 0 && (
        <div className="flex flex-col gap-3" aria-live="polite">
          {turns.map((t, i) =>
            t.role === "user" ? (
              <p key={i} className="ml-auto max-w-[80%] rounded-card bg-surface-2 px-3.5 py-2 text-[14px] text-fg">
                {t.text}
              </p>
            ) : (
              <div key={i} className="flex max-w-[90%] gap-2.5">
                <span className="mt-1 grid size-6 shrink-0 place-items-center rounded-full bg-primary text-primary-fg" aria-hidden>
                  <Sparkle size={12} weight="fill" />
                </span>
                <div className="flex flex-col gap-2">
                  <p className="text-[14px] leading-relaxed text-fg">{t.text}</p>
                  {t.understood && <UnderstoodChips u={t.understood} />}
                </div>
              </div>
            ),
          )}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
        className="flex flex-col gap-3 rounded-card border border-line bg-surface p-3 transition-colors focus-within:border-line-strong"
      >
        <label htmlFor="intent" className="px-1 pt-1 text-xs font-medium text-subtle">
          {answering ? "Your answer" : "Your request"}
        </label>
        <textarea
          id="intent"
          rows={answering ? 2 : 3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(text);
            }
          }}
          className="w-full resize-none bg-transparent px-1 text-[15px] leading-relaxed text-fg outline-none placeholder:text-subtle"
          placeholder={answering ? "Type your answer, or pick one below." : "I'm moving next month and need furniture and kitchen basics."}
        />
        <div className="flex items-center justify-between gap-3">
          {answering ? (
            <button type="button" onClick={reset} className="flex items-center gap-1.5 px-1 text-xs text-muted hover:text-fg">
              <ArrowCounterClockwise size={12} aria-hidden /> Start over
            </button>
          ) : (
            <p className="px-1 text-xs text-subtle">Nothing is bought without your approval.</p>
          )}
          <Button type="submit" disabled={!text.trim() || busy} aria-label={answering ? "Send answer" : "Start"}>
            {busy ? "Thinking" : answering ? "Send" : "Start"} <ArrowUp size={16} weight="bold" aria-hidden />
          </Button>
        </div>
      </form>

      {error && (
        <p role="status" className="text-sm text-negative">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {(answering ? (lastAssistant?.suggestions ?? []) : SUGGESTIONS).map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => (answering ? send(s) : setText(s))}
            className="press rounded-full border border-line px-3 py-1.5 text-left text-[13px] text-muted transition-colors hover:border-line-strong hover:text-fg disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

/** What PersonalIQ took from the request so far, so the user can see it was understood correctly. */
function UnderstoodChips({ u }: { u: Understood }) {
  const chips: string[] = [];
  if (u.template) chips.push(`Goal: ${u.template} setup`);
  for (const n of u.needs.slice(0, 4)) chips.push(needLabel(n.need));
  if (u.budget) chips.push(`Budget ${formatMoney(u.budget, u.currency)}`);
  if (u.deadline) chips.push(`By ${new Date(u.deadline).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <span key={c} className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
          {c}
        </span>
      ))}
      <Tooltip label={u.understood_by === "nemotron" ? "Read by Nemotron, then checked by PersonalIQ's rules. Budgets always come from your words." : "Read by PersonalIQ's built-in rules (the AI model wasn't available)."}>
        <span tabIndex={0} className={cn("cursor-help rounded-full px-2 py-0.5 text-xs", u.understood_by === "nemotron" ? "bg-accent-soft text-accent-ink" : "text-subtle")}>
          {u.understood_by === "nemotron" ? "Nemotron" : "Rules"}
        </span>
      </Tooltip>
    </div>
  );
}
