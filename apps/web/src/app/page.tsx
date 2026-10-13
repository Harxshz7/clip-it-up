"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Scissors,
  ArrowRight,
  Zap,
  Shield,
  Sparkles,
  CheckCircle2,
  Play,
  Film,
  Layers,
  Wand2,
  Clock,
  ChevronDown,
  HelpCircle,
  CreditCard,
  Lock,
  Globe,
  Loader2,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { PlanBillingItem } from "@clip-it-up/shared";

const DEMO_PROJECT_URL = "/videos/00000000-0000-0000-0000-000000000099/clips";

export default function LandingPage() {
  const setUploadModalOpen = useAppStore((s) => s.setUploadModalOpen);
  const openUpgradeModal = useAppStore((s) => s.openUpgradeModal);

  const [currency, setCurrency] = useState<"INR" | "USD">("INR");
  const [plans, setPlans] = useState<PlanBillingItem[]>([]);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [loadingCheckout, setLoadingCheckout] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBillingPlans()
      .then((res) => {
        setPlans(res.plans.filter((p) => p.is_public));
        if (res.currency_default === "USD") setCurrency("USD");
      })
      .catch((err) => {
        console.warn("Using offline fallback plans:", err);
        setPlans([
          {
            key: "free",
            name: "Free",
            description: "Try out AI clipping with your first project",
            price_inr_monthly: 0,
            price_usd_monthly: 0,
            monthly_source_minutes: 30,
            max_exports_per_month: 3,
            watermark: true,
            max_video_length_min: 15,
            max_concurrent_jobs: 1,
            retention_days: 7,
            priority: 1,
            features: ["30 mins source video/mo", "3 exports/mo", "Subtle watermark", "Standard 1080p"],
            is_public: true,
          },
          {
            key: "creator",
            name: "Creator",
            description: "For active podcasters, solo creators, and YouTubers",
            price_inr_monthly: 1499,
            price_usd_monthly: 19,
            monthly_source_minutes: 120,
            max_exports_per_month: 25,
            watermark: false,
            max_video_length_min: 60,
            max_concurrent_jobs: 2,
            retention_days: 30,
            priority: 2,
            features: [
              "120 mins source video/mo",
              "25 clean exports/mo (No watermark)",
              "Smart reframing & auto-tracking",
              "Custom caption styles & filler removal",
              "Priority queue Level 2",
            ],
            is_public: true,
          },
          {
            key: "pro",
            name: "Pro",
            badge: "Most Popular",
            description: "For agencies and serious video production teams",
            price_inr_monthly: 3999,
            price_usd_monthly: 49,
            monthly_source_minutes: 360,
            max_exports_per_month: 100,
            watermark: false,
            max_video_length_min: 120,
            max_concurrent_jobs: 4,
            retention_days: 90,
            priority: 3,
            features: [
              "360 mins source video/mo",
              "100 exports/mo",
              "Zero watermark & 4K exports",
              "Top queue priority Level 3",
              "Dedicated GST tax invoices & priority support",
            ],
            is_public: true,
          },
        ]);
      });
  }, []);

  const handleCheckout = async (planKey: string) => {
    if (planKey === "free") {
      window.location.href = "/dashboard";
      return;
    }

    try {
      setLoadingCheckout(planKey);
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
        window.location.href = `/settings/billing?plan=${planKey}`;
      }
    } catch (err: any) {
      console.error("Checkout error:", err);
      openUpgradeModal(err.message || "Please subscribe from your billing dashboard.");
    } finally {
      setLoadingCheckout(null);
    }
  };

  const faqs = [
    {
      q: "Who owns my uploaded videos and exported clips?",
      a: "You retain 100% full ownership of your source media and all generated clips. clip-it-up only processes your media to generate clips. We explicitly do not use your videos, audio, or transcripts to train public AI models.",
    },
    {
      q: "Can I try the product before uploading my own video?",
      a: "Yes! Click 'Try Interactive Demo' below. We have a pre-processed demo video with AI-ranked clips, captions, and 9:16 reframe ready for you to preview, edit, and export right now with zero signup and zero quota usage.",
    },
    {
      q: "What video formats and file limits are supported?",
      a: "We support MP4, MOV, MKV, and WebM up to 200MB (free tier) and up to 2GB on paid plans. Videos can be up to 120 minutes long.",
    },
    {
      q: "How does billing and GST work for creators in India?",
      a: "We support instant Razorpay subscriptions in Indian Rupees (INR) with UPI, Netbanking, and Cards. For Indian businesses, provide your GSTIN at checkout to receive compliant GST tax invoices (CGST + SGST or IGST) with sequential FY numbering.",
    },
    {
      q: "What happens if I exceed my monthly minute quota?",
      a: "You can easily upgrade your plan or purchase one-off top-up minute packs anytime from your billing settings. Your existing projects and exported clips remain fully accessible.",
    },
    {
      q: "What is your refund policy?",
      a: "We offer a 7-day refund guarantee if you have not consumed substantial processing quota. You can cancel your subscription anytime with 1 click; your access continues until the end of your billing cycle.",
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center pt-6 pb-20 space-y-24">
      {/* 1. Hero Section */}
      <section className="text-center max-w-4xl space-y-6 pt-4">
        <div className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-4 py-1.5 text-xs font-semibold text-purple-300 backdrop-blur-md shadow-inner">
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          <span>Next-Gen Video Intelligence • Launching for Creators</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.1]">
          Turn 60-minute videos into <br />
          <span className="gradient-text">viral clips in 60 seconds</span>
        </h1>

        <p className="text-base sm:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          The autonomous AI clipping engine that identifies peak narrative moments, crops speaker-tracking 9:16 reframes, and generates stylish captions with zero manual scrubbing.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <Link
            href={DEMO_PROJECT_URL}
            className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 px-8 py-4 text-sm font-bold text-white shadow-xl shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 hover:scale-105 active:scale-95 transition-all"
          >
            <Play className="w-4 h-4 fill-white" />
            Try Sample Video (Zero Upload)
          </Link>

          <button
            onClick={() => setUploadModalOpen(true)}
            className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-7 py-4 text-sm font-semibold text-zinc-300 hover:text-white hover:bg-white/10 active:scale-95 transition-all"
          >
            <Scissors className="w-4 h-4 text-purple-400" />
            Upload Your Video
          </button>
        </div>

        <div className="flex items-center justify-center gap-6 pt-2 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> No credit card needed to test
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Razorpay & UPI support
          </span>
        </div>
      </section>

      {/* 2. Interactive Before/After Visual Demo */}
      <section className="w-full max-w-5xl glass-panel-glow rounded-3xl p-6 sm:p-10 border border-purple-500/20 relative overflow-hidden">
        <div className="text-center max-w-xl mx-auto mb-8 space-y-2">
          <h2 className="text-2xl font-bold text-white">Before vs. After In Action</h2>
          <p className="text-xs sm:text-sm text-zinc-400">
            Raw widescreen interview footage transformed into 3 punchy, high-engagement vertical shorts.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
          {/* Before: Raw Long Video */}
          <div className="md:col-span-5 bg-zinc-950/80 rounded-2xl p-4 border border-white/10 space-y-3">
            <div className="flex items-center justify-between text-xs text-zinc-400">
              <span className="font-semibold text-zinc-300">Raw Source (16:9)</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">45:00 Widescreen</span>
            </div>
            <div className="aspect-video bg-zinc-900 rounded-xl relative overflow-hidden border border-white/5 flex items-center justify-center">
              <Film className="w-10 h-10 text-zinc-600" />
              <div className="absolute bottom-2 left-2 right-2 p-2 rounded bg-black/70 backdrop-blur-sm text-[10px] text-zinc-400">
                Monotonous unedited talk, pauses, filler words, static camera angle
              </div>
            </div>
            <div className="text-xs text-zinc-500 space-y-1">
              <div className="flex justify-between">
                <span>Pacing:</span>
                <span className="text-zinc-400">Slow / Uncut</span>
              </div>
              <div className="flex justify-between">
                <span>Format:</span>
                <span className="text-zinc-400">Horizontal only</span>
              </div>
            </div>
          </div>

          {/* Transformation Arrow */}
          <div className="md:col-span-2 flex flex-col items-center justify-center text-center py-2">
            <div className="h-10 w-10 rounded-full bg-purple-600/20 border border-purple-500/40 text-purple-300 flex items-center justify-center shadow-lg">
              <Wand2 className="w-5 h-5 animate-pulse" />
            </div>
            <span className="text-[11px] font-bold text-purple-300 mt-2">AI Clipping</span>
            <span className="text-[10px] text-zinc-500">& Reframe</span>
          </div>

          {/* After: 3 Captioned Clips */}
          <div className="md:col-span-5 bg-purple-950/20 rounded-2xl p-4 border border-purple-500/30 space-y-3">
            <div className="flex items-center justify-between text-xs text-purple-300">
              <span className="font-semibold text-white">3 Viral Shorts (9:16)</span>
              <span className="text-[11px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-semibold">
                Ready to Publish
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="aspect-[9/16] bg-zinc-900 rounded-lg border border-purple-500/40 p-2 flex flex-col justify-between text-[9px]">
                <span className="px-1 py-0.5 rounded bg-purple-500/30 text-purple-200 font-bold">Score 94</span>
                <div className="bg-black/80 p-1 rounded text-center font-bold text-amber-300">
                  "THIS CHANGES EVERYTHING"
                </div>
              </div>
              <div className="aspect-[9/16] bg-zinc-900 rounded-lg border border-purple-500/40 p-2 flex flex-col justify-between text-[9px]">
                <span className="px-1 py-0.5 rounded bg-purple-500/30 text-purple-200 font-bold">Score 89</span>
                <div className="bg-black/80 p-1 rounded text-center font-bold text-sky-300">
                  "THE 3-STEP TRICK"
                </div>
              </div>
              <div className="aspect-[9/16] bg-zinc-900 rounded-lg border border-purple-500/40 p-2 flex flex-col justify-between text-[9px]">
                <span className="px-1 py-0.5 rounded bg-purple-500/30 text-purple-200 font-bold">Score 86</span>
                <div className="bg-black/80 p-1 rounded text-center font-bold text-emerald-300">
                  "WHY MOST FAIL"
                </div>
              </div>
            </div>
            <div className="text-xs text-zinc-400 space-y-1">
              <div className="flex justify-between">
                <span>Enhancements:</span>
                <span className="text-purple-300 font-medium">Kinetic captions + face track</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 text-center">
          <Link
            href={DEMO_PROJECT_URL}
            className="inline-flex items-center gap-2 text-xs font-semibold text-purple-400 hover:text-purple-300 transition-colors"
          >
            <span>Open live interactive editor for this sample project</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </section>

      {/* 3. How It Works (3 Steps) */}
      <section className="w-full max-w-5xl space-y-10">
        <div className="text-center max-w-xl mx-auto space-y-2">
          <h2 className="text-3xl font-bold text-white tracking-tight">How It Works</h2>
          <p className="text-xs sm:text-sm text-zinc-400">
            From raw footage to published viral content in three autonomous steps.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-4">
            <div className="h-10 w-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold text-base">
              1
            </div>
            <h3 className="text-base font-bold text-white">Direct S3 Ingest & Diarization</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Upload directly to high-speed cloud storage. Audio is automatically extracted, transcribed with word-level timestamps, and diarized by speaker.
            </p>
          </div>

          <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-4">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-base">
              2
            </div>
            <h3 className="text-base font-bold text-white">AI Candidate Scoring & Reframe</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Deep LLM heuristics analyze emotional peaks, strong hooks, and standalone narrative value. YOLO face tracking keeps the active speaker centered in 9:16.
            </p>
          </div>

          <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-base">
              3
            </div>
            <h3 className="text-base font-bold text-white">Studio Polish & 1-Click Export</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Fine-tune in our timeline studio: swap hooks, silence filler words, pick TikTok caption styles, and export clean MP4s ready for social distribution.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Key Differentiators */}
      <section className="w-full max-w-5xl glass-panel rounded-3xl p-8 sm:p-12 border border-white/5 space-y-8">
        <div className="text-center max-w-xl mx-auto space-y-2">
          <h2 className="text-2xl sm:text-3xl font-bold text-white">Engineered For Real Creators</h2>
          <p className="text-xs sm:text-sm text-zinc-400">
            No gimmicks. Built to save editors 10+ hours per episode.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="space-y-2">
            <div className="h-9 w-9 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-white">Why-Chosen Reasoning</h4>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Every clip includes an explanation of its narrative hook, retention score, and viral trigger.
            </p>
          </div>

          <div className="space-y-2">
            <div className="h-9 w-9 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Zap className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-white">Hook Swap Engine</h4>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Don't like the intro? Swap with alternate opening hooks extracted from later in the sentence.
            </p>
          </div>

          <div className="space-y-2">
            <div className="h-9 w-9 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center">
              <Scissors className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-white">Filler & Silence Removal</h4>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Automated removal of "um", "ah", "like", and awkward dead air with zero audio pops or clicks.
            </p>
          </div>

          <div className="space-y-2">
            <div className="h-9 w-9 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-white">Platform Presets</h4>
            <p className="text-xs text-zinc-400 leading-relaxed">
              One-click presets for TikTok, YouTube Shorts, Instagram Reels, and LinkedIn square videos.
            </p>
          </div>
        </div>
      </section>

      {/* 5. Dynamic Pricing Section */}
      <section id="pricing" className="w-full max-w-5xl space-y-10">
        <div className="text-center max-w-xl mx-auto space-y-3">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Predictable, Creator-Friendly Pricing
          </h2>
          <p className="text-xs sm:text-sm text-zinc-400">
            Pay for the source minutes you process. No hidden per-clip export royalties.
          </p>

          {/* Currency Toggle */}
          <div className="flex items-center justify-center gap-2 pt-2">
            <span className="text-xs text-zinc-400 font-medium">Select Currency:</span>
            <div className="inline-flex p-0.5 rounded-xl bg-zinc-900 border border-white/10 text-xs shadow-inner">
              <button
                onClick={() => setCurrency("INR")}
                className={`px-3.5 py-1.5 rounded-lg font-semibold transition-all ${
                  currency === "INR"
                    ? "bg-purple-600 text-white shadow-md"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                ₹ INR (India & UPI)
              </button>
              <button
                onClick={() => setCurrency("USD")}
                className={`px-3.5 py-1.5 rounded-lg font-semibold transition-all ${
                  currency === "USD"
                    ? "bg-purple-600 text-white shadow-md"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                $ USD (International)
              </button>
            </div>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isPro = p.key === "pro";
            const isCreator = p.key === "creator";
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
                className={`relative rounded-3xl p-6 sm:p-7 border flex flex-col justify-between transition-all ${
                  isCreator
                    ? "glass-panel-glow border-purple-500/50 bg-gradient-to-b from-purple-950/40 to-zinc-950/70 shadow-xl"
                    : "glass-panel border-white/10 hover:border-white/20"
                }`}
              >
                {isCreator && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-gradient-to-r from-purple-500 to-indigo-500 text-[10px] font-bold uppercase tracking-wider text-white shadow-md">
                    Recommended For Solo Creators
                  </span>
                )}

                <div className="space-y-5">
                  <div>
                    <h3 className="text-xl font-bold text-white capitalize">{p.name}</h3>
                    <p className="text-xs text-zinc-400 mt-1 min-h-[32px]">{p.description}</p>
                  </div>

                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl sm:text-4xl font-extrabold text-white">{price}</span>
                    <span className="text-xs text-zinc-500 font-medium">/month</span>
                  </div>

                  <div className="h-px bg-white/10" />

                  <ul className="space-y-2.5 text-xs text-zinc-300">
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        <strong>{p.monthly_source_minutes} mins</strong> source video per month
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        <strong>{p.max_exports_per_month}</strong> exported clips per month
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        {p.watermark ? "Includes watermark" : "Zero watermark on exports"}
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        Max video length: <strong>{p.max_video_length_min} mins</strong>
                      </span>
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>
                        {p.retention_days} days cloud storage retention
                      </span>
                    </li>
                  </ul>
                </div>

                <button
                  onClick={() => handleCheckout(p.key)}
                  disabled={loadingCheckout !== null}
                  className={`mt-8 w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold transition-all shadow-md active:scale-95 ${
                    isCreator
                      ? "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-purple-500/25"
                      : "bg-white/10 hover:bg-white/20 text-white"
                  }`}
                >
                  {loadingCheckout === p.key ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>{p.key === "free" ? "Get Started Free" : `Subscribe to ${p.name}`}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        <div className="text-center text-xs text-zinc-500">
          All prices exclude applicable GST for Indian businesses. Secure subscriptions via Razorpay & Stripe.
        </div>
      </section>

      {/* 6. FAQ Section */}
      <section className="w-full max-w-3xl space-y-6">
        <div className="text-center max-w-md mx-auto space-y-2">
          <h2 className="text-2xl sm:text-3xl font-bold text-white">Frequently Asked Questions</h2>
          <p className="text-xs sm:text-sm text-zinc-400">
            Clear answers on ownership, billing, and formats.
          </p>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openFaq === idx;
            return (
              <div
                key={idx}
                className="glass-panel rounded-2xl border border-white/5 overflow-hidden transition-all"
              >
                <button
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between p-4 sm:p-5 text-left text-sm font-semibold text-white hover:text-purple-300 transition-colors"
                >
                  <span>{faq.q}</span>
                  <ChevronDown
                    className={`w-4 h-4 text-zinc-400 transition-transform ${
                      isOpen ? "rotate-180 text-purple-400" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 text-xs text-zinc-400 leading-relaxed border-t border-white/5 pt-3">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* 7. Bottom CTA */}
      <section className="w-full max-w-5xl rounded-3xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-purple-900/40 p-8 sm:p-12 border border-purple-500/30 text-center space-y-6">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-white">
          Ready to supercharge your content workflow?
        </h2>
        <p className="text-xs sm:text-sm text-zinc-300 max-w-lg mx-auto">
          Start with our precomputed sample video or upload your latest podcast now.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href={DEMO_PROJECT_URL}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-white px-7 py-3.5 text-xs sm:text-sm font-bold text-zinc-900 hover:bg-zinc-100 shadow-xl transition-all"
          >
            <Play className="w-4 h-4 fill-zinc-900 text-zinc-900" />
            Try Sample Video
          </Link>
          <button
            onClick={() => setUploadModalOpen(true)}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-purple-600 px-7 py-3.5 text-xs sm:text-sm font-bold text-white hover:bg-purple-500 shadow-xl shadow-purple-500/25 transition-all"
          >
            <Scissors className="w-4 h-4" />
            Upload Your Video
          </button>
        </div>
      </section>
    </div>
  );
}
