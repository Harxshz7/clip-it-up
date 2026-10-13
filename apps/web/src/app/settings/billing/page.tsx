"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CreditCard,
  CheckCircle2,
  AlertTriangle,
  Zap,
  ArrowRight,
  Shield,
  Download,
  Clock,
  Sparkles,
  RefreshCw,
  PlusCircle,
  FileText,
  AlertCircle,
  Loader2,
  Calendar,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  PlanBillingItem,
  UserBillingMe,
  TopUpPackItem,
  InvoiceListItem,
} from "@clip-it-up/shared";

export default function BillingSettingsPage() {
  const [billingMe, setBillingMe] = useState<UserBillingMe | null>(null);
  const [plans, setPlans] = useState<PlanBillingItem[]>([]);
  const [topUpPacks, setTopUpPacks] = useState<TopUpPackItem[]>([]);
  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [currency, setCurrency] = useState<"INR" | "USD">("INR");
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [plansRes, meRes, invRes] = await Promise.all([
        api.getBillingPlans().catch(() => ({ plans: [], top_up_packs: [], currency_default: "INR" })),
        api.getBillingMe().catch(() => null),
        api.getInvoices().catch(() => []),
      ]);

      setPlans(plansRes.plans.filter((p) => p.is_public));
      setTopUpPacks(plansRes.top_up_packs);
      if (plansRes.currency_default === "USD") setCurrency("USD");
      setBillingMe(meRes);
      setInvoices(invRes);
    } catch (err: any) {
      console.error("Failed to load billing:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCheckout = async (planKey: string) => {
    try {
      setActionLoading(`checkout-${planKey}`);
      setMessage(null);
      const res = await api.createCheckout({
        plan_key: planKey,
        currency,
      });

      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else if (res.session_id && (window as any).Razorpay && res.provider === "razorpay") {
        const options = {
          key: res.key_id,
          subscription_id: res.session_id,
          name: "clip-it-up",
          description: `Subscription to ${planKey.toUpperCase()}`,
          handler: function () {
            setMessage({ text: "Payment successful! Refreshing subscription...", type: "success" });
            setTimeout(fetchData, 1500);
          },
        };
        const rzp = new (window as any).Razorpay(options);
        rzp.open();
      } else {
        setMessage({ text: "Checkout initialized.", type: "success" });
      }
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to start checkout.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleBuyTopUp = async (packKey: string) => {
    try {
      setActionLoading(`topup-${packKey}`);
      setMessage(null);
      const res = await api.buyTopUp({
        pack_key: packKey,
        currency,
      });

      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        setMessage({ text: `Top-up purchased successfully!`, type: "success" });
        await fetchData();
      }
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to buy top-up.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancelSubscription = async () => {
    if (!confirm("Are you sure you want to cancel your subscription? You will retain access until the end of your billing cycle.")) {
      return;
    }

    try {
      setActionLoading("cancel");
      setMessage(null);
      await api.cancelSubscription();
      setMessage({ text: "Subscription cancelled. Access remains active until period end.", type: "success" });
      await fetchData();
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to cancel subscription.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleResumeSubscription = async () => {
    try {
      setActionLoading("resume");
      setMessage(null);
      await api.resumeSubscription();
      setMessage({ text: "Subscription successfully resumed!", type: "success" });
      await fetchData();
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to resume subscription.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </div>
    );
  }

  const currentPlan = billingMe?.plan;
  const usage = billingMe?.usage;
  const sub = billingMe?.subscription;
  const minutesPct = usage ? Math.min(100, Math.round((usage.source_minutes_used / Math.max(1, usage.source_minutes_limit)) * 100)) : 0;
  const exportsPct = usage ? Math.min(100, Math.round((usage.exports_used / Math.max(1, usage.exports_limit)) * 100)) : 0;

  return (
    <div className="space-y-10 pb-16">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <CreditCard className="w-7 h-7 text-purple-400" />
            <span>Plans & Billing</span>
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            Manage your subscription tier, track quota usage, download tax invoices, and add top-ups.
          </p>
        </div>

        {/* Currency Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Currency:</span>
          <div className="inline-flex p-0.5 rounded-xl bg-zinc-900 border border-white/10 text-xs shadow-inner">
            <button
              onClick={() => setCurrency("INR")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                currency === "INR" ? "bg-purple-600 text-white shadow-md" : "text-zinc-400 hover:text-white"
              }`}
            >
              ₹ INR
            </button>
            <button
              onClick={() => setCurrency("USD")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all ${
                currency === "USD" ? "bg-purple-600 text-white shadow-md" : "text-zinc-400 hover:text-white"
              }`}
            >
              $ USD
            </button>
          </div>
        </div>
      </div>

      {message && (
        <div
          className={`p-4 rounded-2xl border text-xs flex items-center gap-2.5 ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-red-500/10 border-red-500/30 text-red-300"
          }`}
        >
          {message.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* 1. Current Plan & Usage Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Current Plan Overview Card */}
        <div className="glass-panel-glow rounded-3xl p-6 border border-purple-500/30 space-y-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider">Current Tier</span>
            {sub && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                sub.status === "active" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
              }`}>
                {sub.status}
              </span>
            )}
          </div>

          <div>
            <h2 className="text-2xl font-bold text-white capitalize">{currentPlan?.name || "Free"}</h2>
            <p className="text-xs text-zinc-400 mt-1">{currentPlan?.description || "Basic clipping with watermark"}</p>
          </div>

          <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2 text-xs">
            <div className="flex justify-between text-zinc-400">
              <span>Billing Cycle:</span>
              <span className="text-white font-medium">Monthly</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Cycle Reset:</span>
              <span className="text-white font-medium">{billingMe?.reset_date ? new Date(billingMe.reset_date).toLocaleDateString() : "Next Month"}</span>
            </div>
            {billingMe?.top_up_minutes_balance ? (
              <div className="flex justify-between text-emerald-400">
                <span>Top-up Reserve:</span>
                <span className="font-bold">{billingMe.top_up_minutes_balance} mins</span>
              </div>
            ) : null}
          </div>

          {sub?.cancel_at_period_end ? (
            <div className="space-y-2">
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Subscription cancels on {new Date(sub.current_period_end).toLocaleDateString()}</span>
              </div>
              <button
                onClick={handleResumeSubscription}
                disabled={actionLoading !== null}
                className="w-full py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition-all shadow-md"
              >
                {actionLoading === "resume" ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Resume Subscription"}
              </button>
            </div>
          ) : sub?.status === "active" ? (
            <button
              onClick={handleCancelSubscription}
              disabled={actionLoading !== null}
              className="w-full py-2 px-3 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-red-500/10 hover:border-red-500/30 text-xs font-semibold text-zinc-400 hover:text-red-300 transition-all"
            >
              {actionLoading === "cancel" ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Cancel Subscription"}
            </button>
          ) : null}
        </div>

        {/* Meter: Source Minutes Usage */}
        <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-4 flex flex-col justify-between">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-400" />
                <span>Source Minutes</span>
              </h3>
              <span className="text-xs font-semibold text-purple-300">{minutesPct}% used</span>
            </div>
            <p className="text-xs text-zinc-400">Total duration of uploaded videos processed this cycle.</p>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-white font-bold">{usage?.source_minutes_used || 0} mins</span>
              <span className="text-zinc-400">Limit: {usage?.source_minutes_limit || 30} mins</span>
            </div>
            <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  minutesPct >= 90 ? "bg-red-500" : minutesPct >= 70 ? "bg-amber-500" : "bg-purple-500"
                }`}
                style={{ width: `${minutesPct}%` }}
              />
            </div>
          </div>

          <div className="text-[11px] text-zinc-500 flex items-center justify-between pt-2 border-t border-white/5">
            <span>Remaining: {usage?.source_minutes_remaining || 0} mins</span>
            <span>Refreshes monthly</span>
          </div>
        </div>

        {/* Meter: Exports Used */}
        <div className="glass-panel rounded-3xl p-6 border border-white/5 space-y-4 flex flex-col justify-between">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-indigo-400" />
                <span>Monthly Exports</span>
              </h3>
              <span className="text-xs font-semibold text-indigo-300">{exportsPct}% used</span>
            </div>
            <p className="text-xs text-zinc-400">Number of viral 9:16 clips rendered and exported.</p>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-white font-bold">{usage?.exports_used || 0} clips</span>
              <span className="text-zinc-400">Limit: {usage?.exports_limit || 3} clips</span>
            </div>
            <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  exportsPct >= 90 ? "bg-red-500" : exportsPct >= 70 ? "bg-amber-500" : "bg-indigo-500"
                }`}
                style={{ width: `${exportsPct}%` }}
              />
            </div>
          </div>

          <div className="text-[11px] text-zinc-500 flex items-center justify-between pt-2 border-t border-white/5">
            <span>Remaining: {usage?.exports_remaining || 0} clips</span>
            <span>{currentPlan?.watermark ? "With Watermark" : "Zero Watermark"}</span>
          </div>
        </div>
      </div>

      {/* 2. Upgrade / Change Plan Section */}
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-white">Available Plans</h2>
          <p className="text-xs text-zinc-400 mt-1">Upgrade or switch plans. Upgrades apply immediately with proration.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isCurrent = currentPlan?.key === p.key;
            const price =
              currency === "INR"
                ? p.price_inr_monthly === 0
                  ? "₹0"
                  : `₹${p.price_inr_monthly}`
                : p.price_usd_monthly === 0
                ? "$0"
                : `$${p.price_usd_monthly}`;

            return (
              <div
                key={p.key}
                className={`glass-panel rounded-3xl p-6 border flex flex-col justify-between transition-all ${
                  isCurrent
                    ? "border-purple-500/50 bg-purple-950/20"
                    : "border-white/5 hover:border-white/20"
                }`}
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-base font-bold text-white capitalize">{p.name}</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">{p.description}</p>
                    </div>
                    {isCurrent && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40">
                        Current
                      </span>
                    )}
                  </div>

                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-extrabold text-white">{price}</span>
                    <span className="text-xs text-zinc-500">/mo</span>
                  </div>

                  <div className="h-px bg-white/10" />

                  <ul className="space-y-2 text-xs text-zinc-300">
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{p.monthly_source_minutes} mins source processing</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{p.max_exports_per_month} exported clips/mo</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{p.watermark ? "Watermark included" : "Zero watermark"}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>Queue priority Level {p.priority}</span>
                    </li>
                  </ul>
                </div>

                <button
                  onClick={() => handleCheckout(p.key)}
                  disabled={isCurrent || actionLoading !== null}
                  className={`mt-6 w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-md ${
                    isCurrent
                      ? "bg-white/5 text-zinc-500 cursor-not-allowed"
                      : "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-purple-500/20 active:scale-95"
                  }`}
                >
                  {actionLoading === `checkout-${p.key}` ? (
                    <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                  ) : isCurrent ? (
                    "Active Tier"
                  ) : (
                    `Switch to ${p.name}`
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* 3. Top-Up Minute Packs */}
      {topUpPacks.length > 0 && (
        <div className="glass-panel rounded-3xl p-6 sm:p-8 border border-white/5 space-y-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <PlusCircle className="w-5 h-5 text-purple-400" />
              <span>Need More Minutes Right Now?</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Purchase one-off minute packs without upgrading your monthly subscription plan. Top-up minutes expire after 90 days.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {topUpPacks.map((pack) => {
              const packPrice = currency === "INR" ? `₹${pack.price_inr}` : `$${pack.price_usd}`;
              return (
                <div key={pack.key} className="p-4 rounded-2xl bg-zinc-900/60 border border-white/10 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white">{pack.name}</h4>
                    <span className="text-sm font-extrabold text-purple-300">{packPrice}</span>
                  </div>
                  <p className="text-xs text-zinc-400">
                    Adds <strong>{pack.minutes} extra source minutes</strong> to your account.
                  </p>
                  <button
                    onClick={() => handleBuyTopUp(pack.key)}
                    disabled={actionLoading !== null}
                    className="w-full py-2 px-3 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-semibold text-white transition-all active:scale-95"
                  >
                    {actionLoading === `topup-${pack.key}` ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Buy Pack"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Invoices and Receipts History */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-400" />
              <span>Invoices & Receipts</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Sequential, gap-free GST tax invoices and receipts with full tax breakdown.
            </p>
          </div>
        </div>

        {invoices.length === 0 ? (
          <div className="glass-panel rounded-2xl p-8 text-center text-zinc-500 text-xs">
            No invoices generated yet. Invoices appear here automatically upon subscription renewal or top-up payment.
          </div>
        ) : (
          <div className="glass-panel rounded-2xl border border-white/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-zinc-300">
                <thead className="bg-white/[0.03] text-zinc-400 uppercase text-[10px] tracking-wider border-b border-white/5">
                  <tr>
                    <th className="px-5 py-3">Invoice #</th>
                    <th className="px-5 py-3">Date</th>
                    <th className="px-5 py-3">Subtotal</th>
                    <th className="px-5 py-3">Tax</th>
                    <th className="px-5 py-3">Total</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-5 py-3.5 font-mono font-semibold text-white">{inv.invoice_number}</td>
                      <td className="px-5 py-3.5 text-zinc-400">{new Date(inv.created_at).toLocaleDateString()}</td>
                      <td className="px-5 py-3.5">{inv.currency} {inv.amount_subtotal}</td>
                      <td className="px-5 py-3.5">{inv.currency} {inv.amount_tax}</td>
                      <td className="px-5 py-3.5 font-bold text-white">{inv.currency} {inv.amount_total}</td>
                      <td className="px-5 py-3.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                          inv.status === "paid" ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-800 text-zinc-400"
                        }`}>
                          {inv.status}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <a
                          href={api.getInvoiceDownloadUrl(inv.id)}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-purple-300 hover:text-white transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>PDF</span>
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
