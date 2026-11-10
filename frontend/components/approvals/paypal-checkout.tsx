"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowsClockwise, CheckCircle, CircleNotch, PaypalLogo, WarningCircle, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Section } from "@/components/ui/section";
import { Stat } from "@/components/ui/stat";
import { Tooltip } from "@/components/ui/tooltip";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";
import type { ApprovalView, PaymentView, PayPalConfig } from "@/types/api";

// ---- PayPal JS SDK, loaded once per page ----

type PayPalButtons = { render: (el: HTMLElement) => Promise<void>; close: () => Promise<void> };
type PayPalNamespace = {
  Buttons: (opts: {
    style?: Record<string, string | number>;
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID: string }, actions: { restart: () => Promise<void> }) => Promise<void>;
    onCancel?: (data: { orderID: string }) => void;
    onError?: (err: unknown) => void;
  }) => PayPalButtons;
};
declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

let sdkPromise: Promise<PayPalNamespace> | null = null;
function loadSdk(clientId: string, currency: string): Promise<PayPalNamespace> {
  if (window.paypal) return Promise.resolve(window.paypal);
  sdkPromise ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=${currency}&intent=capture&components=buttons`;
    s.onload = () => (window.paypal ? resolve(window.paypal) : reject(new Error("PayPal SDK missing")));
    s.onerror = () => {
      sdkPromise = null;
      reject(new Error("Couldn't load PayPal"));
    };
    document.head.appendChild(s);
  });
  return sdkPromise;
}

type ApiDetail = { code?: string; message?: string; approval_id?: string };
function detailOf(e: unknown): ApiDetail {
  if (e instanceof ApiError) {
    try {
      return JSON.parse(e.message) as ApiDetail;
    } catch {
      return { message: e.message };
    }
  }
  return { message: "Something went wrong." };
}

const PAYABLE = new Set(["approved", "awaiting_buyer_checkout"]);

export function PayPalCheckout({ a, onChange }: { a: ApprovalView; onChange: () => void }) {
  const router = useRouter();
  const [config, setConfig] = useState<PayPalConfig | null>(null);
  const [sdkError, setSdkError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<PaymentView | null>(null); // shown once, right after a verified capture
  const holder = useRef<HTMLDivElement>(null);

  const p: PaymentView = a.payment;
  const status = p.order_status;
  const orderId = a.order.id;
  const payable = PAYABLE.has(status);

  useEffect(() => {
    apiGet<PayPalConfig>("/payments/paypal/config").then(setConfig).catch(() => setSdkError("Couldn't reach the API."));
  }, []);

  // Render the PayPal buttons while the order can be paid.
  useEffect(() => {
    if (!payable || !config?.enabled || !config.client_id || !config.currency || !holder.current) return;
    let buttons: PayPalButtons | null = null;
    let gone = false;
    loadSdk(config.client_id, config.currency)
      .then((paypal) => {
        if (gone || !holder.current) return;
        buttons = paypal.Buttons({
          style: { layout: "vertical", shape: "rect", label: "pay", height: 40 },
          createOrder: async () => {
            setError(null);
            setNotice(null);
            try {
              const r = await apiPost<{ paypal_order_id: string }>("/payments/paypal/create-order", { order_id: orderId });
              return r.paypal_order_id;
            } catch (e) {
              const d = detailOf(e);
              setError(d.message ?? "Couldn't start PayPal checkout.");
              if (d.code === "reapproval_required" && d.approval_id) router.push(`/approvals/${d.approval_id}`);
              throw e;
            }
          },
          onApprove: async (data, actions) => {
            setBusy(true);
            try {
              const r = await apiPost<PaymentView>("/payments/paypal/capture-order", { order_id: orderId, paypal_order_id: data.orderID });
              if (r.order_status === "paid" && r.verified && !r.already_captured) setSuccess(r);
              else if (r.order_status !== "paid") setNotice(r.message || "PayPal hasn't confirmed the payment yet.");
            } catch (e) {
              const d = detailOf(e);
              if (d.code === "instrument_declined") {
                setError(d.message ?? "PayPal declined that payment method.");
                return actions.restart();
              }
              setError(d.message ?? "The payment couldn't be completed.");
            } finally {
              setBusy(false);
              onChange();
            }
          },
          onCancel: (data) => {
            setNotice("You closed PayPal. Nothing was charged.");
            apiPost("/payments/paypal/checkout-cancelled", { order_id: orderId, paypal_order_id: data.orderID }).catch(() => {}).finally(onChange);
          },
          onError: () => setError((prev) => prev ?? "PayPal checkout ran into a problem. Nothing was charged."),
        });
        return buttons.render(holder.current);
      })
      .catch(() => setSdkError("Couldn't load PayPal checkout. Check your connection or ad blocker."));
    return () => {
      gone = true;
      buttons?.close().catch(() => {});
    };
  }, [payable, config, orderId, onChange, router]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(detailOf(e).message ?? "Something went wrong.");
    } finally {
      setBusy(false);
      onChange();
    }
  }

  const homeCur = a.order.currency;
  const charge = a.charge;
  const converted = charge.currency !== homeCur;

  return (
    <Section title="Payment" description="PayPal Sandbox. The amount comes from the approved order on the server, never from this page." icon={<PaypalLogo size={14} />}>
      <div className="flex flex-col gap-4 rounded-card border border-line p-5">
        {/* What will be charged */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-subtle">{status === "paid" ? "Charged by PayPal" : "PayPal will charge"}</span>
            <span className="tabular text-2xl font-semibold tracking-tight text-fg">
              {formatMoney(charge.total, charge.currency)} <span className="text-sm font-medium text-subtle">{charge.currency}</span>
            </span>
            {converted && (
              <Tooltip label="The demo catalog is priced in USD, and PayPal only accepts INR for PayPal India accounts. Rates are fixed demo rates, not live.">
                <span tabIndex={0} className="cursor-help text-[13px] text-muted">
                  Your order total is {formatMoney(a.order.total, homeCur)}. {charge.rate_note}.
                </span>
              </Tooltip>
            )}
          </div>
          <div className="flex flex-col items-end gap-1 text-xs text-subtle">
            <span>{a.items.length} items</span>
            <span>{a.order.merchants.join(", ")}</span>
          </div>
        </div>

        {/* State */}
        {status === "paid" && (
          <Note tone="positive" icon={<CheckCircle size={18} weight="fill" />} title="Paid, verified with PayPal" body="PayPal confirmed the capture for the approved amount and currency.">
            <div className="flex flex-wrap gap-x-5 gap-y-2 pt-1">
              {p.paypal_order_id && <Stat label="PayPal order" value={p.paypal_order_id} />}
              {p.capture_id && <Stat label="Capture" value={p.capture_id} />}
              {p.verified_at && <Stat label="Verified" value={new Date(p.verified_at).toLocaleString()} />}
            </div>
            <Link href={`/purchases/${orderId}`} className="w-fit pt-1 text-[13px] font-medium text-fg underline underline-offset-4">
              View the decision receipt
            </Link>
          </Note>
        )}
        {status === "capturing" && (
          <Note tone="neutral" icon={<CircleNotch size={18} className="animate-spin" />} title="Confirming with PayPal" body="Don't close this page." />
        )}
        {status === "reconciliation_required" && (
          <Note tone="caution" icon={<WarningCircle size={18} weight="fill" />} title="Checking the payment with PayPal" body={p.message || "The outcome isn't confirmed yet. It is not marked paid."}>
            {p.id && (
              <div className="pt-1">
                <Button variant="secondary" disabled={busy} onClick={() => run(() => apiPost(`/payments/${p.id}/reconcile`, {}))}>
                  <ArrowsClockwise size={14} aria-hidden /> Check with PayPal
                </Button>
              </div>
            )}
          </Note>
        )}
        {status === "failed" && <Note tone="negative" icon={<X size={18} />} title="Payment failed" body={p.message || "PayPal didn't complete the payment. Nothing was charged."} />}
        {status === "cancelled" && <Note tone="neutral" icon={<X size={18} />} title="Order cancelled" body="You cancelled before paying. Nothing was charged." />}
        {status === "expired" && <Note tone="negative" icon={<X size={18} />} title="Approval expired" body="Approved orders must be paid within 24 hours. Start the request again from Home." />}

        {payable && (
          <div className="flex flex-col gap-3 border-t border-line pt-4">
            {!config ? (
              <div className="skeleton h-10 w-full" aria-busy="true" aria-label="Loading PayPal" />
            ) : !config.enabled ? (
              <p className="text-[13px] text-negative">PayPal isn&apos;t configured on the server. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in backend/.env.</p>
            ) : sdkError ? (
              <p className="text-[13px] text-negative">{sdkError}</p>
            ) : (
              <div className={cn("w-full max-w-[420px]", busy && "pointer-events-none opacity-50")} ref={holder} />
            )}
            <p className="text-xs text-subtle">Log in with your PayPal Sandbox personal (buyer) account. No real money moves.</p>
          </div>
        )}

        {(error || notice) && <p className={cn("text-[13px]", error ? "text-negative" : "text-muted")}>{error ?? notice}</p>}

        <Dialog
          open={success !== null}
          onClose={() => setSuccess(null)}
          icon={<CheckCircle size={16} weight="fill" className="text-positive" />}
          title="Payment successful"
          subtitle="PayPal confirmed the capture, and it matches the order you approved."
          footer={
            <>
              <Button variant="ghost" onClick={() => router.push(`/purchases/${orderId}`)}>
                View decision receipt
              </Button>
              <Button onClick={() => router.push("/")}>
                Plan your next purchase <ArrowRight size={14} aria-hidden />
              </Button>
            </>
          }
        >
          {success && (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <span className="tabular text-2xl font-semibold tracking-tight text-fg">
                  {formatMoney(success.amount ?? charge.total, success.currency ?? charge.currency)}{" "}
                  <span className="text-sm font-medium text-subtle">{success.currency}</span>
                </span>
                {converted && <span className="text-[13px] text-muted">Your order total was {formatMoney(a.order.total, homeCur)}.</span>}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {success.paypal_order_id && <Stat label="PayPal order" value={success.paypal_order_id} />}
                {success.capture_id && <Stat label="Capture" value={success.capture_id} />}
              </div>
              <p className="rounded-card border border-line bg-surface px-4 py-3 text-[13px] text-muted">
                Keep it going. Tell us what you need next on Home, and it will be planned, budget-checked and brought back for your approval the same way.
              </p>
            </div>
          )}
        </Dialog>

        {payable && (
          <div className="flex justify-end">
            <Tooltip label="Call off this order. Nothing has been charged yet.">
              <Button variant="danger" disabled={busy} onClick={() => run(() => apiPost(`/payments/orders/${orderId}/cancel`, {}))}>
                <X size={14} aria-hidden /> Cancel order
              </Button>
            </Tooltip>
          </div>
        )}
      </div>
    </Section>
  );
}

function Note({ tone, icon, title, body, children }: { tone: "positive" | "negative" | "caution" | "neutral"; icon: React.ReactNode; title: string; body: string; children?: React.ReactNode }) {
  const cls = {
    positive: "border-positive/40 bg-positive/5 text-positive",
    negative: "border-negative/40 bg-negative/5 text-negative",
    caution: "border-caution/40 bg-caution/5 text-caution",
    neutral: "border-line text-muted",
  }[tone];
  return (
    <div className={cn("flex items-start gap-3 rounded-card border px-4 py-3", cls)}>
      <span className="mt-0.5 shrink-0" aria-hidden>
        {icon}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-[14px] font-semibold text-fg">{title}</p>
        <p className="text-[13px] text-muted">{body}</p>
        {children}
      </div>
    </div>
  );
}
