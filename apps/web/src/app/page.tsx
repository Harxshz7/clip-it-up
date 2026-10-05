"use client";

import Link from "next/link";
import { Scissors, ArrowRight, Zap, Shield, Sparkles, Layers, RefreshCw } from "lucide-react";
import { useAppStore } from "@/lib/store";

export default function LandingPage() {
  const setUploadModalOpen = useAppStore((s) => s.setUploadModalOpen);

  return (
    <div className="flex flex-col items-center justify-center pt-8 pb-16 space-y-16">
      {/* Hero Section */}
      <div className="text-center max-w-3xl space-y-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-500/10 px-3.5 py-1 text-xs font-semibold text-purple-300 backdrop-blur-sm shadow-inner">
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          <span>Phase 0 Foundation • Realtime SSE Pipeline</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-tight">
          Turn long videos into <br />
          <span className="gradient-text">viral clips in seconds</span>
        </h1>

        <p className="text-base sm:text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          High-performance distributed media architecture. Direct S3 upload with presigned URLs,
          asynchronous Celery execution, and live streaming progress updates via SSE.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <button
            onClick={() => setUploadModalOpen(true)}
            className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 px-7 py-3.5 text-sm font-semibold text-white shadow-xl shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 hover:scale-105 active:scale-95 transition-all"
          >
            <Scissors className="w-4 h-4" />
            Upload Video & Test Pipeline
          </button>
          <Link
            href="/dashboard"
            className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-7 py-3.5 text-sm font-semibold text-zinc-300 hover:text-white hover:bg-white/10 active:scale-95 transition-all"
          >
            View Dashboard
            <ArrowRight className="w-4 h-4 text-zinc-400" />
          </Link>
        </div>
      </div>

      {/* Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl">
        <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-3">
          <div className="h-10 w-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400">
            <Zap className="w-5 h-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Direct S3 / MinIO Upload</h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Zero bottleneck on backend API. Browser streams directly to storage via presigned PUT URLs or chunked multipart upload.
          </p>
        </div>

        <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
          <h3 className="text-base font-semibold text-white">6-Stage Distributed Pipeline</h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Celery worker executes ingest, proxy, transcribe, candidates, score, and render stages idempotently with per-stage INR cost tracking.
          </p>
        </div>

        <div className="glass-panel rounded-2xl p-6 border border-white/5 space-y-3">
          <div className="h-10 w-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400">
            <RefreshCw className="w-5 h-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Server-Sent Events (SSE)</h3>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Instant snapshot hydration, Redis pub/sub live updates, 15s heartbeats, and Last-Event-ID automatic reconnect.
          </p>
        </div>
      </div>
    </div>
  );
}
