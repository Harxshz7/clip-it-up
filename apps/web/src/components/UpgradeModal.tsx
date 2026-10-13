"use client";

import { useEffect, useState } from "react";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { PlanBillingItem } from "@clip-it-up/shared";
import {
  X,
  Sparkles,
  CheckCircle2,
  Zap,
  ArrowRight,
  Shield,
  CreditCard,
  Loader2,
  AlertTriangle,
} from "lucide-react";

export function UpgradeModal() {
  const { isUpgradeModalOpen, upgradeModalReason, closeUpgradeModal } = useAppStore();
  const [plans, setPlans] = useState<PlanBillingItem[]>([]);
  const [currency, setCurrency] = useState<"INR" | "USD">("INR");
  const [loading, setLoading] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    if (isUpgradeModalOpen && plans.length === 0) {
      setLoading(true);
      api
        .getBillingPlans()
        .then((res) => {
          setPlans(res.plans.filter((p) => p.is_public));
          if (res.currency_default === "USD") setCurrency("USD");
        })
        .catch((err) => console.error("Failed to load plans:", err))
        .finally(() => setLoading(false));
    }
  }, [isUpgradeModalOpen, plans.length]);

  if (!isUpgradeModalOpen) return null;

  const handleCheckout = async (planKey: string) => {
    try {
      setCheckoutLoading(planKey);
      const res = await api.createCheckout({
        plan_key: planKey,
        currency: currency,
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
            window.location.href = "/settings/billing?success=true";
          },
        };
        const rzp = new (window as any).Razorpay(options);
        rzp.open();
      } else {
        // Fallback to billing settings
        window.location.href = `/settings/billing?plan=${planKey}`;
      }
    } catch (err: any) {
      console.error("Checkout failed:", err);
      alert(err.message || "Failed to start checkout. Redirecting to billing page.");
      window.location.href = "/settings/billing";
    } finally {
      setCheckoutLoading(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl glass-panel-glow rounded-3xl p-6 sm:p-8 border border-purple-500/30 text-white shadow-2xl">
        {/* Close Button */}
        <button
          onClick={closeUpgradeModal}
          className="absolute top-5 right-5 text-zinc-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="text-center max-w-lg mx-auto space-y-3 mb-6">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-xs font-semibold border border-purple-500/30">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Unlock Creator Power</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Level up your video clipping
          </h2>

          {upgradeModalReason ? (
            <div className="inline-flex items-center gap-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs text-left">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{upgradeModalReason}</span>
            </div>
          ) : (
            <p className="text-xs sm:text-sm text-zinc-400">
              Remove watermarks, process up to 300 minutes per month, and get 4K high-bitrate exports.
            </p>
          )}

          {/* Currency Toggle */}
          <div className="flex items-center justify-center gap-2 pt-2">
            <span className="text-xs text-zinc-400 font-medium">Currency:</span>
            <div className="inline-flex p-0.5 rounded-lg bg-zinc-900 border border-white/10 text-xs">
              <button
                onClick={() => setCurrency("INR")}
                className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                  currency === "INR"
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                ₹ INR
              </button>
              <button
                onClick={() => setCurrency("USD")}
                className={`px-2.5 py-1 rounded-md font-semibold transition-all ${
                  currency === "USD"
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                $ USD
              </button>
            </div>
          </div>
        </div>

        {/* Plans Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
            {plans
              .filter((p) => p.key !== "free")
              .map((plan) => {
                const isPro = plan.key === "pro";
                const price =
                  currency === "INR"
                    ? `₹${plan.price_inr_monthly}`
                    : `$${plan.price_usd_monthly}`;

                return (
                  <div
                    key={plan.key}
                    className={`relative rounded-2xl p-5 border transition-all flex flex-col justify-between ${
                      isPro
                        ? "bg-gradient-to-b from-purple-900/30 to-zinc-900/50 border-purple-500/50 shadow-lg shadow-purple-500/10"
                        : "bg-zinc-900/70 border-white/10 hover:border-white/20"
                    }`}
                  >
                    {isPro && (
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-purple-500 to-indigo-500 text-[10px] font-bold uppercase tracking-wider text-white shadow-sm">
                        Best Value
                      </span>
                    )}

                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-bold text-white capitalize">{plan.name}</h3>
                          <p className="text-xs text-zinc-400">{plan.description}</p>
                        </div>
                        <div className="text-right">
                          <span className="text-2xl font-extrabold text-white">{price}</span>
                          <span className="text-xs text-zinc-500">/mo</span>
                        </div>
                      </div>

                      <div className="h-px bg-white/10" />

                      <ul className="space-y-2 text-xs text-zinc-300">
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>
                            <strong>{plan.monthly_source_minutes} mins</strong> source processing / month
                          </span>
                        </li>
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>
                            <strong>{plan.max_exports_per_month}</strong> exported viral clips / month
                          </span>
                        </li>
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>
                            {plan.watermark ? "Watermarked" : "Zero watermark (clean exports)"}
                          </span>
                        </li>
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>
                            Max video length: <strong>{plan.max_video_length_min} mins</strong>
                          </span>
                        </li>
                        <li className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                          <span>
                            Priority queue: Level {plan.priority} fast processing
                          </span>
                        </li>
                      </ul>
                    </div>

                    <button
                      onClick={() => handleCheckout(plan.key)}
                      disabled={checkoutLoading !== null}
                      className={`mt-6 w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all shadow-md active:scale-95 ${
                        isPro
                          ? "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-purple-500/20"
                          : "bg-white/10 hover:bg-white/20 text-white"
                      }`}
                    >
                      {checkoutLoading === plan.key ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <span>Upgrade to {plan.name}</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
          </div>
        )}

        {/* Footer Guarantee */}
        <div className="flex flex-col sm:flex-row items-center justify-between text-[11px] text-zinc-500 pt-3 border-t border-white/5 gap-2">
          <div className="flex items-center gap-2">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>Secure billing via Razorpay & Stripe • 7-day refund policy for unconsumed minutes</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Cancel anytime</span>
            <span>•</span>
            <span>Instant invoice & GST receipts</span>
          </div>
        </div>
      </div>
    </div>
  );
}
