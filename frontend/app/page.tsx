import { ChatCircleDots, Path, SealCheck, ShieldCheck, Target, UsersThree } from "@phosphor-icons/react/dist/ssr";
import { IntentComposer } from "@/components/home/intent-composer";
import { RecentObjectives } from "@/components/home/recent-objectives";
import { Section } from "@/components/ui/section";

const FLOW = [
  { title: "Understand", body: "Reads your goal, budget and deadline. Asks if something is missing.", icon: ChatCircleDots },
  { title: "Plan and research", body: "Five agents split the work: needs, products, cart, budget, follow-up.", icon: UsersThree },
  { title: "You approve", body: "You see the exact items, total and reasons. Nothing moves until you say yes.", icon: SealCheck },
  { title: "Pay and verify", body: "PayPal Sandbox runs the payment. PersonalIQ records it only once it's confirmed.", icon: ShieldCheck },
];

export default function HomePage() {
  return (
    <div className="flex max-w-[860px] flex-col gap-10">
      <section className="flex flex-col gap-6">
        {/* Two-tone heading: statement, then a muted continuation in the same font. */}
        <h2 className="max-w-[32ch] text-2xl font-semibold leading-tight tracking-[-0.02em] text-fg md:text-[30px]">
          What should PersonalIQ take care of? <span className="text-muted">It plans, checks your budget, and buys only what you approve.</span>
        </h2>
        <IntentComposer />
      </section>

      <Section title="Active objectives" description="Your recent requests. Click one to see what the agents did." icon={<Target size={14} />}>
        <RecentObjectives />
      </Section>

      <Section title="How a request moves" description="Four steps, and you're in control at the third." icon={<Path size={14} />}>
        <ol className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FLOW.map(({ title, body, icon: Icon }, i) => (
            <li key={title} className="flex flex-col gap-2 rounded-card border border-line p-4">
              <span className="flex items-center gap-2">
                <span className="grid size-7 place-items-center rounded-control border border-line bg-surface text-muted">
                  <Icon size={14} aria-hidden />
                </span>
                <span className="tabular text-xs text-subtle">{i + 1}</span>
              </span>
              <p className="text-[13px] font-semibold text-fg">{title}</p>
              <p className="text-[13px] leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
