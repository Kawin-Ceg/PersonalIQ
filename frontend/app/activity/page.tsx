import { Suspense } from "react";
import { ActivityView } from "@/components/activity/activity-view";

export default function ActivityPage() {
  return (
    <Suspense fallback={<div className="skeleton h-40 w-full max-w-[860px]" aria-busy="true" aria-label="Loading" />}>
      <ActivityView />
    </Suspense>
  );
}
