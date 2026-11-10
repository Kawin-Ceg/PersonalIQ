"use client";

import { useState } from "react";
import { Brain, CaretRight, ChatCircleText, Star } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Chip, Field, inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { DIMENSION_LABEL } from "@/lib/personal";
import type { Aspect, Dimension, FeedbackItem, Learning, Product } from "@/types/api";
import { LearningResult } from "./learning-result";

const REASONS: Dimension[] = ["durability", "quality", "value", "price"];
const RATINGS = Array.from({ length: 10 }, (_, i) => ({ value: i + 1, label: String(i + 1) }));
const ASPECTS: { key: Aspect; label: string }[] = [
  { key: "quality", label: "Quality" },
  { key: "durability", label: "Durability" },
  { key: "value", label: "Value for money" },
];
// Five plain steps, stored as 2-10. Poor (2) and Weak (4) teach; OK and up don't change weights.
const ASPECT_SCALE = [
  { value: 2, label: "Poor" },
  { value: 4, label: "Weak" },
  { value: 6, label: "OK" },
  { value: 8, label: "Good" },
  { value: 10, label: "Great" },
];

function ratingTone(r: number) {
  return r <= 5 ? "border-negative/40 text-negative" : r >= 8 ? "border-positive/40 text-positive" : "border-line text-muted";
}

export function FeedbackSection({ items, products, onAdded }: { items: FeedbackItem[]; products: Product[]; onAdded: () => void }) {
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<FeedbackItem | null>(null);

  return (
    <div className="flex flex-col gap-3">
      {items.length > 0 ? (
        <ul className="overflow-hidden rounded-card border border-line">
          {items.map((f) => (
            <li key={f.id} className="border-b border-line last:border-b-0">
              <button onClick={() => setSelected(f)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface">
                <span className={cn("tabular grid h-6 w-11 shrink-0 place-items-center rounded-control border text-xs font-semibold", ratingTone(f.rating))}>{f.rating}/10</span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13px] font-medium text-fg">{f.item_name}</span>
                  <span className="truncate text-xs text-subtle">{f.didnt_work || f.worked || "No notes"}</span>
                </span>
                <CaretRight size={12} className="shrink-0 text-subtle" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-card border border-dashed border-line-strong px-4 py-6 text-[13px] text-muted">
          Tell PersonalIQ how past purchases turned out. A bad experience makes it weigh that problem more next time.
        </p>
      )}

      <Button variant="secondary" className="w-fit" onClick={() => setAdding(true)}>
        <Star size={14} aria-hidden /> Rate a past purchase
      </Button>

      {selected && (
        <Dialog open onClose={() => setSelected(null)} icon={<ChatCircleText size={16} />} title={selected.item_name} subtitle={`Rated ${selected.rating}/10 on ${new Date(selected.created_at).toLocaleDateString()}`}>
          <dl className="flex flex-col gap-3 text-[13px]">
            <Detail label="What worked">{selected.worked || "Nothing noted"}</Detail>
            <Detail label="What didn't">{selected.didnt_work || "Nothing noted"}</Detail>
            <Detail label="Mainly about">{selected.reasons.length ? selected.reasons.map((r) => DIMENSION_LABEL[r]).join(", ") : "Not specified"}</Detail>
            <p className="rounded-card border border-line bg-surface px-3 py-2 text-muted">
              {selected.rating <= 5
                ? "PersonalIQ now leaves this exact product out, and weighs the problems you picked more for similar items."
                : selected.rating >= 8
                  ? "PersonalIQ now scores this product a little higher for you."
                  : "A middling rating is noted but doesn't change rankings."}
            </p>
          </dl>
        </Dialog>
      )}

      {adding && (
        <FeedbackDialog
          products={products}
          onClose={() => setAdding(false)}
          onDone={() => {
            setAdding(false);
            onAdded();
          }}
        />
      )}
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="text-fg">{children}</dd>
    </div>
  );
}

/** Rate something. With `fixed`, it rates one item from a PersonalIQ purchase (tied to the order). */
export function FeedbackDialog({
  products = [],
  fixed,
  onDone,
  onClose,
}: {
  products?: Product[];
  fixed?: { productId: string; name: string; orderId: string };
  onDone: () => void;
  onClose: () => void;
}) {
  const [productId, setProductId] = useState(fixed?.productId ?? "");
  const [itemName, setItemName] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [aspects, setAspects] = useState<Partial<Record<Aspect, number>>>({});
  const [worked, setWorked] = useState("");
  const [didntWork, setDidntWork] = useState("");
  const [reasons, setReasons] = useState<Dimension[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [learned, setLearned] = useState<Learning | null>(null);

  const canSave = (productId || itemName.trim()) && rating !== null && !busy;

  function setAspect(a: Aspect, v: number) {
    setAspects((prev) => {
      const next = { ...prev };
      if (next[a] === v) delete next[a]; // click again to clear
      else next[a] = v;
      return next;
    });
  }

  async function submit() {
    if (!canSave) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await apiPost<FeedbackItem>("/me/feedback", {
        product_id: productId || null,
        item_name: productId ? null : itemName.trim(),
        order_id: fixed?.orderId ?? null,
        rating,
        aspects: productId ? aspects : {},
        worked,
        didnt_work: didntWork,
        reasons,
      });
      if (saved.learning) {
        setLearned(saved.learning); // show what changed before closing
        setBusy(false);
      } else onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^"|"$/g, "") : "Could not save");
      setBusy(false);
    }
  }

  if (learned) {
    return (
      <Dialog
        open
        onClose={onDone}
        icon={<Brain size={16} />}
        title={learned.changed ? "What changed because of your rating" : "Thanks, saved"}
        subtitle={`Same ranking as before, run again for ${learned.need.replace(/_/g, " ")} in ${learned.category}.`}
        footer={<Button onClick={onDone}>Done</Button>}
      >
        <LearningResult learning={learned} />
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onClose={onClose}
      icon={<Star size={16} />}
      title={fixed ? `How is the ${fixed.name}?` : "Rate a past purchase"}
      subtitle={fixed ? "Your answer changes how similar items are ranked for you next time." : "Low ratings teach PersonalIQ what to avoid."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="positive" disabled={!canSave} onClick={submit}>
            {busy ? "Saving" : "Save feedback"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {!fixed && (
          <Field label="Product from the catalog" htmlFor="fb-product">
            <select id="fb-product" value={productId} onChange={(e) => setProductId(e.target.value)} className={inputClass}>
              <option value="">Not in the catalog</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {!fixed && !productId && (
          <Field label="Or name it" htmlFor="fb-name">
            <input id="fb-name" value={itemName} onChange={(e) => setItemName(e.target.value)} className={inputClass} placeholder="Gaming laptop" />
          </Field>
        )}
        <Field label="Overall, how happy are you with it?" hint="1 is very unhappy, 10 is very happy. 5 or less means it won't be suggested again.">
          <Segmented<number> label="Rating" value={rating} onChange={setRating} options={RATINGS} />
        </Field>
        {productId && (
          <Field label="How did each part hold up?" hint="Optional. A poor score makes that matter more for this kind of product next time. Click again to clear.">
            <div className="flex flex-col gap-2">
              {ASPECTS.map((a) => (
                <div key={a.key} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[13px] text-fg">{a.label}</span>
                  <Segmented<number> label={a.label} value={aspects[a.key] ?? null} onChange={(v) => setAspect(a.key, v)} options={ASPECT_SCALE} />
                </div>
              ))}
            </div>
          </Field>
        )}
        <Field label="What worked" htmlFor="fb-worked">
          <input id="fb-worked" value={worked} onChange={(e) => setWorked(e.target.value)} className={inputClass} />
        </Field>
        <Field label="What didn't" htmlFor="fb-didnt">
          <input id="fb-didnt" value={didntWork} onChange={(e) => setDidntWork(e.target.value)} className={inputClass} />
        </Field>
        {!productId && (
          <Field label="Was it mainly about" hint="Low ratings raise the importance of what you pick here.">
            <div className="flex flex-wrap gap-2">
              {REASONS.map((r) => (
                <Chip key={r} selected={reasons.includes(r)} onClick={() => setReasons(reasons.includes(r) ? reasons.filter((x) => x !== r) : [...reasons, r])}>
                  {DIMENSION_LABEL[r]}
                </Chip>
              ))}
            </div>
          </Field>
        )}
        {error && <p className="text-[13px] text-negative">{error}</p>}
      </div>
    </Dialog>
  );
}
