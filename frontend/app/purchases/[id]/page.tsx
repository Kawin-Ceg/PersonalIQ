"use client";

import { useParams } from "next/navigation";
import { ReceiptView } from "@/components/purchases/receipt-view";

export default function ReceiptPage() {
  const { id } = useParams<{ id: string }>();
  return <ReceiptView key={id} orderId={id} />;
}
