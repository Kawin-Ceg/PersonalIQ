"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Chip, Field, inputClass } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { apiPost } from "@/lib/api";
import { DIMENSION_LABEL } from "@/lib/personal";
import type { Dimension, Level, Merchant, OnboardingInput, UserContext } from "@/types/api";

const DIMENSIONS: Dimension[] = ["durability", "quality", "value", "price"];

function initialFrom(ctx: UserContext): OnboardingInput {
  const stated = DIMENSIONS.filter((d) => ctx.importance[d].source === "user_stated" && ctx.importance[d].level !== "low");
  const rank = (d: Dimension) => (ctx.importance[d].level === "high" ? 0 : 1);
  stated.sort((a, b) => rank(a) - rank(b));
  const monthly = ctx.budgets.find((b) => b.name === "Monthly discretionary");
  return {
    priorities: stated.slice(0, 2),
    price_sensitivity: ctx.price_sensitivity.source === "default" ? "medium" : ctx.price_sensitivity.level,
    avoid_materials: ctx.avoid_materials,
    like_merchants: ctx.like_merchants,
    avoid_merchants: ctx.avoid_merchants,
    likes: ctx.likes,
    dislikes: ctx.dislikes,
    monthly_budget: monthly?.limit_amount ?? null,
  };
}

const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
const splitList = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export function OnboardingForm({
  ctx,
  materials,
  merchants,
  onSaved,
  onCancel,
  bare = false,
}: {
  ctx: UserContext;
  materials: string[];
  merchants: Merchant[];
  onSaved: (ctx: UserContext) => void;
  onCancel?: () => void;
  bare?: boolean; // inside a dialog: no card around it
}) {
  const [form, setForm] = useState<OnboardingInput>(() => initialFrom(ctx));
  const [likes, setLikes] = useState(form.likes.join(", "));
  const [dislikes, setDislikes] = useState(form.dislikes.join(", "));
  const [budget, setBudget] = useState(form.monthly_budget ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof OnboardingInput>(k: K, v: OnboardingInput[K]) => setForm((f) => ({ ...f, [k]: v }));
  const budgetValid = budget === "" || /^\d{1,9}(\.\d{1,2})?$/.test(budget.trim());

  function pickPriority(d: Dimension) {
    if (form.priorities.includes(d)) set("priorities", form.priorities.filter((x) => x !== d));
    else if (form.priorities.length < 2) set("priorities", [...form.priorities, d]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!budgetValid) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await apiPost<UserContext>("/me/onboarding", {
        ...form,
        likes: splitList(likes),
        dislikes: splitList(dislikes),
        monthly_budget: budget.trim() || null,
      });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className={bare ? "flex flex-col gap-6" : "flex flex-col gap-6 rounded-card border border-line bg-surface p-5 md:p-6"}>
      <Field label="What matters most when you buy something?" hint="Pick up to two. The first one counts most.">
        <div className="flex flex-wrap gap-2">
          {DIMENSIONS.map((d) => {
            const rank = form.priorities.indexOf(d);
            return (
              <Chip key={d} selected={rank >= 0} onClick={() => pickPriority(d)}>
                {rank >= 0 && <span className="tabular mr-1.5 text-subtle">{rank + 1}</span>}
                {DIMENSION_LABEL[d]}
              </Chip>
            );
          })}
        </div>
      </Field>

      <Field label="How careful are you with price?">
        <Segmented<Level>
          label="Price sensitivity"
          value={form.price_sensitivity}
          onChange={(v) => set("price_sensitivity", v)}
          options={[
            { value: "low", label: "Not very" },
            { value: "medium", label: "Somewhat" },
            { value: "high", label: "Very" },
          ]}
        />
      </Field>

      <Field label="Materials to avoid" hint="Products with these are left out of recommendations.">
        <div className="flex flex-wrap gap-2">
          {materials.map((m) => (
            <Chip key={m} selected={form.avoid_materials.includes(m)} onClick={() => set("avoid_materials", toggle(form.avoid_materials, m))}>
              {m}
            </Chip>
          ))}
        </div>
      </Field>

      <div className="flex flex-col gap-6">
        <Field label="Stores you like">
          <div className="flex flex-wrap gap-2">
            {merchants.map((m) => (
              <Chip
                key={m.slug}
                selected={form.like_merchants.includes(m.slug)}
                onClick={() => {
                  set("like_merchants", toggle(form.like_merchants, m.slug));
                  set("avoid_merchants", form.avoid_merchants.filter((x) => x !== m.slug));
                }}
              >
                {m.name}
              </Chip>
            ))}
          </div>
        </Field>
        <Field label="Stores to avoid">
          <div className="flex flex-wrap gap-2">
            {merchants.map((m) => (
              <Chip
                key={m.slug}
                selected={form.avoid_merchants.includes(m.slug)}
                onClick={() => {
                  set("avoid_merchants", toggle(form.avoid_merchants, m.slug));
                  set("like_merchants", form.like_merchants.filter((x) => x !== m.slug));
                }}
              >
                {m.name}
              </Chip>
            ))}
          </div>
        </Field>
      </div>

      <div className="flex flex-col gap-6">
        <Field label="Things you like" hint="Separate with commas." htmlFor="likes">
          <input id="likes" value={likes} onChange={(e) => setLikes(e.target.value)} className={inputClass} placeholder="Minimal design, quiet appliances" />
        </Field>
        <Field label="Things you dislike" hint="Separate with commas." htmlFor="dislikes">
          <input id="dislikes" value={dislikes} onChange={(e) => setDislikes(e.target.value)} className={inputClass} placeholder="Glossy finishes" />
        </Field>
      </div>

      <Field label={`Monthly spending budget (${ctx.currency})`} hint={budgetValid ? "Optional. Used to flag purchases that would go over." : undefined} htmlFor="budget">
        <input
          id="budget"
          inputMode="decimal"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          className={`${inputClass} max-w-48`}
          placeholder={ctx.currency === "INR" ? "85000" : "1000"}
          aria-invalid={!budgetValid}
        />
        {!budgetValid && <p className="text-xs text-negative">Enter a plain amount like 85000 or 1000.50.</p>}
      </Field>

      {error && <p className="text-[13px] text-negative">{error}</p>}

      <div className="flex gap-2">
        <Button type="submit" variant="positive" disabled={saving || !budgetValid}>
          {saving ? "Saving" : "Save preferences"}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
