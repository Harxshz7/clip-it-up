import { AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";

export const metadata = {
  title: "Refund & Cancellation Policy | clip-it-up",
  description: "Subscription cancellation terms, refund eligibility, and credit note issuance.",
};

export default function RefundPage() {
  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8 text-zinc-300 text-sm leading-relaxed">
      {/* Notice Banner */}
      <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <strong>DRAFT - REQUIRES FORMAL LEGAL REVIEW:</strong> Commercial cancellation and refund guidelines.
        </div>
      </div>

      <div className="space-y-2 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-extrabold text-white">Refund & Cancellation Policy</h1>
        <p className="text-xs text-zinc-500">Version 1.0 • Effective Date: October 13, 2026</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">1. Subscription Cancellation</h2>
        <p>
          You may cancel your monthly subscription at any time directly through the <strong>Plans & Billing</strong> settings in your dashboard or by notifying support. Cancellation takes effect at the end of your current monthly billing period. You retain complete access to all paid features and your unused quota until your period expires.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">2. 7-Day Refund Guarantee</h2>
        <p>
          We provide a 7-day refund window for first-time subscribers. If you are unsatisfied with clip-it-up within 7 days of your initial subscription payment and have consumed less than 15% of your allotted source minutes, you may request a full refund by contacting <a href="mailto:support@clipitup.example.com" className="text-purple-400">support@clipitup.example.com</a>.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">3. Top-Up Minute Packs</h2>
        <p>
          One-time top-up minute packs are non-refundable once purchased, as cloud compute and transcribing capacity are provisioned immediately. Top-up minutes remain valid for 90 days from the date of purchase.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white">4. Credit Notes & GST Accounting</h2>
        <p>
          When a refund is approved and processed via Razorpay or Stripe, a formal Credit Note is automatically generated in accordance with GST regulations and provided to you via email and your billing dashboard. Refunds are credited back to the original payment source within 5 to 7 business days.
        </p>
      </section>
    </div>
  );
}
