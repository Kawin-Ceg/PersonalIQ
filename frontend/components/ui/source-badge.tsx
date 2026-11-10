import { cn } from "@/lib/cn";
import { SOURCE_LABEL } from "@/lib/personal";
import type { Source } from "@/types/api";
import { Tooltip } from "./tooltip";

const HINT: Record<Source, string> = {
  user_stated: "You said this yourself. PersonalIQ never overrides it with a guess.",
  uploaded: "Learned from spending data you uploaded.",
  feedback: "Learned from how a past purchase turned out.",
  observed: "Learned from what you did in the app, like products you turned down.",
  inferred: "PersonalIQ's best guess. Correct it if it's wrong.",
  default: "PersonalIQ doesn't know this yet, so it uses a neutral setting.",
};

/** Where a fact came from. The user's own word is visually strongest. */
export function SourceBadge({ source, confidence }: { source: Source; confidence?: number }) {
  const hint = HINT[source] + (confidence !== undefined && confidence < 1 ? ` Confidence ${Math.round(confidence * 100)}%.` : "");
  return (
    <Tooltip label={hint}>
      <span
        tabIndex={0}
        className={cn(
          "inline-flex h-5 shrink-0 cursor-help items-center gap-1 whitespace-nowrap rounded-full border px-2 text-[11px] font-medium",
          source === "user_stated" ? "border-line-strong text-fg" : "border-line text-muted",
          source === "default" && "border-dashed text-subtle",
        )}
      >
        {SOURCE_LABEL[source]}
        {confidence !== undefined && confidence < 1 && <span className="tabular text-subtle">{Math.round(confidence * 100)}%</span>}
      </span>
    </Tooltip>
  );
}
