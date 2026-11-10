"use client";

import { useParams } from "next/navigation";
import { ObjectiveView } from "@/components/objectives/objective-view";

export default function ObjectivePage() {
  const { id } = useParams<{ id: string }>();
  return <ObjectiveView key={id} id={id} />;
}
