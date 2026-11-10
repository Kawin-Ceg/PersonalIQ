"use client";

import { useState } from "react";
import { Brain, CaretRight, Heart, Lightbulb, Prohibit, Storefront, Target } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { SourceBadge } from "@/components/ui/source-badge";
import { apiDelete, apiPatch } from "@/lib/api";
import { SOURCE_LABEL } from "@/lib/personal";
import type { Level, MemoryItem } from "@/types/api";

const GROUPS: { key: string; title: string; types: string[]; icon: React.ReactNode }[] = [
  { key: "priorities", title: "Priorities", types: ["importance"], icon: <Target size={14} /> },
  { key: "avoid", title: "Things to avoid", types: ["exclusion"], icon: <Prohibit size={14} /> },
  { key: "stores", title: "Stores", types: ["merchant"], icon: <Storefront size={14} /> },
  { key: "taste", title: "Likes and dislikes", types: ["like", "dislike"], icon: <Heart size={14} /> },
  { key: "lessons", title: "Lessons from past purchases", types: ["lesson"], icon: <Lightbulb size={14} /> },
];

/** Memories grouped by kind. Click one to see where it came from, correct it, or remove it. */
export function MemoryList({ memories, onChange }: { memories: MemoryItem[]; onChange: () => void }) {
  const [selected, setSelected] = useState<MemoryItem | null>(null);

  if (memories.length === 0) {
    return <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-[13px] text-muted">Nothing remembered yet.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      {GROUPS.map((g) => {
        const items = memories.filter((m) => g.types.includes(m.memory_type));
        if (items.length === 0) return null;
        return (
          <div key={g.key} className="flex flex-col gap-2">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-fg">
              <span className="text-muted">{g.icon}</span>
              {g.title}
              <span className="tabular font-normal text-subtle">{items.length}</span>
            </p>
            <ul className="overflow-hidden rounded-card border border-line">
              {items.map((m) => (
                <li key={m.id} className="border-b border-line last:border-b-0">
                  <button onClick={() => setSelected(m)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface">
                    <span className="min-w-0 flex-1 truncate text-[13px] text-fg">{m.content}</span>
                    <SourceBadge source={m.source} confidence={m.confidence} />
                    <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {selected && <MemoryDialog key={selected.id} m={selected} onClose={() => setSelected(null)} onChange={onChange} />}
    </div>
  );
}

function MemoryDialog({ m, onClose, onChange }: { m: MemoryItem; onClose: () => void; onChange: () => void }) {
  const [text, setText] = useState(m.content);
  const [level, setLevel] = useState<Level | null>(m.meta.level ?? null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changed = m.meta.level ? level !== m.meta.level : text.trim() !== m.content && text.trim() !== "";

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChange();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      icon={<Brain size={16} />}
      title="Memory"
      subtitle={`${SOURCE_LABEL[m.source]}, ${Math.round(m.confidence * 100)}% confidence`}
      footer={
        confirmRemove ? (
          <>
            <span className="mr-auto self-center text-[13px] text-muted">Remove this memory for good?</span>
            <Button variant="ghost" onClick={() => setConfirmRemove(false)}>
              Keep it
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => run(() => apiDelete(`/me/memories/${m.id}`))}>
              Yes, remove
            </Button>
          </>
        ) : (
          <>
            <Button variant="danger" className="mr-auto" onClick={() => setConfirmRemove(true)}>
              Remove
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="positive"
              disabled={busy || !changed}
              onClick={() => run(() => apiPatch(`/me/memories/${m.id}`, m.meta.level ? { level } : { content: text.trim() }))}
            >
              Save correction
            </Button>
          </>
        )
      }
    >
      <div className="flex flex-col gap-4 text-[13px]">
        <p className="text-[14px] leading-relaxed text-fg">{m.content}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-subtle">
          <SourceBadge source={m.source} confidence={m.confidence} />
          <span>Learned {new Date(m.created_at).toLocaleDateString()}</span>
        </div>
        <div className="flex flex-col gap-1.5 border-t border-line pt-4">
          <p className="font-medium text-fg">Correct it</p>
          {m.meta.level ? (
            <Segmented<Level>
              label="How much this matters"
              value={level}
              onChange={setLevel}
              options={[
                { value: "high", label: "High" },
                { value: "medium", label: "Medium" },
                { value: "low", label: "Low" },
              ]}
            />
          ) : (
            <input aria-label="Corrected memory" value={text} onChange={(e) => setText(e.target.value)} className={inputClass} />
          )}
          <p className="text-xs text-subtle">A correction counts as something you told PersonalIQ, so it won&apos;t be overwritten later.</p>
        </div>
        {error && <p className="text-negative">{error}</p>}
      </div>
    </Dialog>
  );
}
