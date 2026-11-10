"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Brain, ChartPieSlice, Eye, Gauge, PencilSimple, Receipt, Scales, Target, UserCircle, Wallet } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { SourceBadge } from "@/components/ui/source-badge";
import { Stat } from "@/components/ui/stat";
import { Tabs } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { DIMENSION_LABEL, LEVEL_LABEL } from "@/lib/personal";
import type { Catalog, Dimension, FeedbackItem, MemoryItem, Signal, UserContext } from "@/types/api";
import { FeedbackSection } from "./feedback-section";
import { MemoryList } from "./memory-list";
import { OnboardingForm } from "./onboarding-form";
import { SpendingPanel } from "./spending-panel";

type Data = { ctx: UserContext; memories: MemoryItem[]; feedback: FeedbackItem[]; catalog: Catalog };
type Tab = "overview" | "memories" | "spending" | "purchases";

const DIMS: Dimension[] = ["durability", "quality", "value", "price"];
const LEVEL_TONE: Record<string, string> = { high: "text-fg font-semibold", medium: "text-muted", low: "text-subtle" };

export function YouView() {
  const [data, setData] = useState<Data | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");

  const load = useCallback(async () => {
    try {
      const [ctx, memories, feedback, catalog] = await Promise.all([
        apiGet<UserContext>("/me/context"),
        apiGet<MemoryItem[]>("/me/memories"),
        apiGet<FeedbackItem[]>("/me/feedback"),
        apiGet<Catalog>("/products"),
      ]);
      setData({ ctx, memories, feedback, catalog });
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const { materials, merchants } = useMemo(() => {
    if (!data) return { materials: [], merchants: [] };
    const mats = new Set(data.catalog.items.flatMap((p) => p.attributes.materials ?? []));
    const bySlug = new Map(data.catalog.items.map((p) => [p.merchant.slug, p.merchant]));
    return { materials: [...mats].sort(), merchants: [...bySlug.values()] };
  }, [data]);

  if (failed) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-card border border-line px-6 py-8">
        <p className="text-[14px] font-medium text-fg">Couldn&apos;t load your profile</p>
        <p className="text-[13px] text-muted">Check that the API is running on port 8000, then try again.</p>
        <Button variant="secondary" onClick={load}>
          Try again
        </Button>
      </div>
    );
  }
  if (!data) return <LoadingState />;

  const { ctx } = data;
  const firstName = ctx.name.split(" ")[0];

  return (
    <>
      <PageHeader
        icon={<UserCircle size={18} />}
        title={ctx.onboarded ? `What PersonalIQ knows about ${firstName}` : `Welcome, ${firstName}`}
        description={
          ctx.onboarded
            ? `Everything here shapes recommendations. Amounts are in ${ctx.currency}. Click anything to see where it came from or correct it.`
            : "Answer a few questions so recommendations fit you. You can change any answer later."
        }
        actions={
          ctx.onboarded ? (
            <Button variant="secondary" onClick={() => setEditing(true)}>
              <PencilSimple size={14} aria-hidden /> Edit preferences
            </Button>
          ) : undefined
        }
      />

      {!ctx.onboarded ? (
        <OnboardingForm ctx={ctx} materials={materials} merchants={merchants} onSaved={load} />
      ) : (
        <>
          <Tabs<Tab>
            label="Profile views"
            value={tab}
            onChange={setTab}
            items={[
              { value: "overview", label: "Overview", icon: <Gauge size={14} /> },
              { value: "memories", label: "Memories", icon: <Brain size={14} />, count: data.memories.length },
              { value: "spending", label: "Spending", icon: <ChartPieSlice size={14} /> },
              { value: "purchases", label: "Past purchases", icon: <Receipt size={14} />, count: data.feedback.length },
            ]}
          />

          {tab === "overview" && (
            <div className="flex max-w-[860px] flex-col gap-10">
              <Section title="Priorities" description="How much each factor counts when PersonalIQ compares products." icon={<Target size={14} />}>
                <ul className="overflow-hidden rounded-card border border-line">
                  {DIMS.map((d) => (
                    <PriorityRow key={d} label={DIMENSION_LABEL[d]} signal={ctx.importance[d]} />
                  ))}
                  <PriorityRow label="Price sensitivity" signal={ctx.price_sensitivity} />
                </ul>
              </Section>

              <Section title="How this shapes ranking" description="The share each factor gets in your product score." icon={<Scales size={14} />}>
                <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-card border border-line px-4 py-3">
                  {(Object.entries(ctx.scoring_weights) as [Dimension | "fit", number][]).map(([k, w]) => (
                    <Stat key={k} label={DIMENSION_LABEL[k]} value={`${Math.round(w * 100)}%`} />
                  ))}
                </div>
              </Section>

              {ctx.budgets.length > 0 && (
                <Section title="Budgets" description="Purchases are checked against these before you're asked to approve." icon={<Wallet size={14} />}>
                  <ul className="overflow-hidden rounded-card border border-line">
                    {ctx.budgets.map((b) => (
                      <li key={b.name} className="flex items-center justify-between border-b border-line px-4 py-3 text-[13px] last:border-b-0">
                        <span className="flex flex-col">
                          <span className="font-medium text-fg">{b.name}</span>
                          <span className="text-xs text-subtle">{b.period === "monthly" ? "Resets every month" : "One-off budget"}</span>
                        </span>
                        <span className="tabular text-[14px] font-semibold text-fg">{formatMoney(b.limit_amount, b.currency)}</span>
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {ctx.recent_interest.length > 0 && (
                <Section title="Recently browsing" description="From products you opened in Discover." icon={<Eye size={14} />}>
                  <p className="text-[13px] text-fg">{ctx.recent_interest.join(", ")}</p>
                </Section>
              )}
            </div>
          )}

          {tab === "memories" && (
            <div className="max-w-[860px]">
              <Section title="Memories" description="The facts behind your profile, grouped by kind." icon={<Brain size={14} />}>
                <MemoryList memories={data.memories} onChange={load} />
              </Section>
            </div>
          )}

          {tab === "spending" && (
            <div className="max-w-[860px]">
              <Section title="Spending" description={`Your last 90 days, in ${ctx.currency}.`} icon={<ChartPieSlice size={14} />}>
                <SpendingPanel spending={ctx.spending} onImported={load} />
              </Section>
            </div>
          )}

          {tab === "purchases" && (
            <div className="max-w-[860px]">
              <Section title="Past purchases" description="What worked and what didn't. Click one for details." icon={<Receipt size={14} />}>
                <FeedbackSection items={data.feedback} products={data.catalog.items} onAdded={load} />
              </Section>
            </div>
          )}
        </>
      )}

      <Dialog open={editing} onClose={() => setEditing(false)} wide icon={<PencilSimple size={16} />} title="Edit preferences" subtitle="Saving replaces your earlier answers. Memories from feedback and spending stay.">
        <OnboardingForm
          bare
          ctx={ctx}
          materials={materials}
          merchants={merchants}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            load();
          }}
        />
      </Dialog>
    </>
  );
}

function PriorityRow({ label, signal }: { label: string; signal: Signal }) {
  const why = signal.source === "default" ? "PersonalIQ doesn't know yet, so this counts as medium." : signal.reason;
  return (
    <li className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0">
      <Tooltip label={why} side="right">
        <span tabIndex={0} className="cursor-help text-[13px] font-medium text-fg">
          {label}
        </span>
      </Tooltip>
      <span className="flex items-center gap-2">
        <span className={`text-[13px] ${LEVEL_TONE[signal.level]}`}>{LEVEL_LABEL[signal.level]}</span>
        <SourceBadge source={signal.source} />
      </span>
    </li>
  );
}

function LoadingState() {
  return (
    <div aria-busy="true" aria-label="Loading profile" className="flex flex-col gap-6">
      <div className="skeleton h-5 w-64" />
      <div className="skeleton h-3 w-96 max-w-full" />
      <div className="skeleton h-10 w-full max-w-[860px]" />
      <div className="skeleton h-64 w-full max-w-[860px]" />
    </div>
  );
}
