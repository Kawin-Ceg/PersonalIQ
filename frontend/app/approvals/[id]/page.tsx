"use client";

import { useParams } from "next/navigation";
import { ApprovalDetail } from "@/components/approvals/approval-detail";

export default function ApprovalPage() {
  const { id } = useParams<{ id: string }>();
  return <ApprovalDetail key={id} id={id} />;
}
