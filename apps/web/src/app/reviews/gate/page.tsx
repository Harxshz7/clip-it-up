"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { GateReport } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
  TrendingUp,
  DollarSign,
  Users,
  Layers,
  RotateCcw,
  Loader2,
  FileText,
  Lightbulb,
} from "lucide-react";

export default function GateReportPage() {
  const [report, setReport] = useState<GateReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getGateReport();
      setReport(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load Gate Decision Report");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <p className="text-sm text-zinc-400">Computing Creator Gate Decision Report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="max-w-md mx-auto my-12 glass-panel p-8 rounded-3xl text-center space-y-4">
        <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Gate Report Error</h2>
        <p className="text-xs text-zinc-400">{error || "Unable to compute gate report."}</p>
        <button
          type="button"
          onClick={fetchReport}
          className="px-4 py-2 rounded-xl bg-purple-600 text-xs font-bold text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  const m = report.metrics;
  const verdict = report.overall_verdict;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-16 font-sans">
      {/* Navigation Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <button
          type="button"
          onClick={fetchReport}
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Refresh Gate Report
        </button>
      </div>

      {/* Decision Header Card */}
      <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-purple-400 uppercase tracking-wider">
              Phase 2.5 Reality Check
            </span>
            <span className="text-zinc-600">•</span>
            <span className="text-xs text-zinc-400 font-mono">{report.timestamp}</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-white">Creator Gate Decision Report</h1>
          <p className="text-xs text-zinc-400 max-w-xl">
            Synthesized evaluation from {m.submitted_creators} creator sessions ({m.total_clips_rated} clips rated) checking whether AI clip selection meets product readiness.
          </p>
        </div>

        {/* Big Decision Badge */}
        <div className="shrink-0 flex flex-col items-center sm:items-end">
          <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 mb-1">
            Overall Gate Decision
          </span>
          <div
            className={`px-5 py-2.5 rounded-2xl border text-sm font-black tracking-wide flex items-center gap-2 shadow-xl ${
              verdict === "GO"
                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-emerald-500/10"
                : verdict === "FIX SELECTION FIRST"
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-amber-500/10"
                : "bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-rose-500/10"
            }`}
          >
            {verdict === "GO" && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
            {verdict === "FIX SELECTION FIRST" && <AlertTriangle className="w-5 h-5 text-amber-400" />}
            {verdict === "RETHINK" && <XCircle className="w-5 h-5 text-rose-400" />}
            <span>{verdict}</span>
          </div>
        </div>
      </div>

      {/* 4 Gate Checks Grid */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
          1. Gate Criteria Evaluation (config/gate.yaml)
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {report.checks.map((c) => {
            const isPass = c.status === "PASS";
            return (
              <div
                key={c.id}
                className={`p-4 rounded-2xl border flex items-start justify-between gap-3 ${
                  isPass
                    ? "bg-emerald-950/15 border-emerald-500/30"
                    : "bg-rose-950/15 border-rose-500/30"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                        isPass ? "bg-emerald-500/30 text-emerald-300" : "bg-rose-500/30 text-rose-300"
                      }`}
                    >
                      {c.status}
                    </span>
                    <h3 className="text-xs font-bold text-white">{c.name}</h3>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{c.message}</p>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-xs font-mono font-bold text-zinc-200 block">{c.actual}</span>
                  <span className="text-[10px] text-zinc-500 font-mono">Target: {c.target}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Metrics Stats */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
          2. Aggregate Quantitative Metrics
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Usable Rate</span>
            <span className="text-lg font-bold text-emerald-400 font-mono">
              {Math.round(m.usable_rate * 100)}%
            </span>
            <span className="text-[10px] text-zinc-500 block">Post as-is + edits</span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Strict Rate</span>
            <span className="text-lg font-bold text-white font-mono">
              {Math.round(m.strict_usable_rate * 100)}%
            </span>
            <span className="text-[10px] text-zinc-500 block">Post as-is only</span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Top 3 vs 8</span>
            <span className="text-lg font-bold text-purple-300 font-mono">
              {Math.round(m.top3_usable_rate * 100)}% / {Math.round(m.top8_usable_rate * 100)}%
            </span>
            <span className="text-[10px] text-zinc-500 block">Ranking lift</span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Score Correlation</span>
            <span className="text-lg font-bold text-white font-mono">
              r = {m.score_verdict_correlation}
            </span>
            <span className="text-[10px] text-zinc-500 block">Model vs Creator</span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Median WTP</span>
            <span className="text-lg font-bold text-emerald-400 font-mono">
              ₹{m.median_open_price_inr.toLocaleString()}/mo
            </span>
            <span className="text-[10px] text-zinc-500 block">{m.accepts_1500_pct}% @ ₹1.5k</span>
          </div>

          <div className="glass-panel p-4 rounded-2xl border border-white/5 space-y-1">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Upload Commit</span>
            <span className="text-lg font-bold text-purple-300 font-mono">
              {m.commit_upload_pct}%
            </span>
            <span className="text-[10px] text-zinc-500 block">Next video intent</span>
          </div>
        </div>
      </div>

      {/* Negative Reasons & Recommendations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Negative Reason Distribution */}
        <div className="lg:col-span-6 space-y-3">
          <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
            3. Rejection Reason Breakdown
          </h2>

          <div className="glass-panel p-5 rounded-3xl border border-white/10 space-y-3">
            {Object.keys(m.reason_distribution || {}).length === 0 ? (
              <p className="text-xs text-zinc-500 italic">No rejection reasons recorded.</p>
            ) : (
              <div className="space-y-2.5 text-xs">
                {Object.entries(m.reason_distribution).map(([tag, pct]) => (
                  <div key={tag} className="space-y-1">
                    <div className="flex justify-between text-zinc-300">
                      <span className="font-mono">{tag}</span>
                      <span className="font-bold text-white font-mono">{pct}%</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-purple-500 to-rose-500 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Top 3 Data-Driven Recommendations */}
        <div className="lg:col-span-6 space-y-3">
          <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Lightbulb className="w-3.5 h-3.5 text-amber-400" /> 4. Top 3 Data-Driven Recommendations
          </h2>

          <div className="glass-panel p-5 rounded-3xl border border-white/10 space-y-3">
            {report.recommendations.map((rec, i) => (
              <div
                key={i}
                className="p-3.5 rounded-2xl bg-zinc-900/80 border border-white/5 flex items-start gap-3 text-xs leading-relaxed"
              >
                <span className="h-5 w-5 rounded-full bg-purple-500/20 text-purple-300 font-bold flex items-center justify-center shrink-0 text-[11px]">
                  {i + 1}
                </span>
                <span className="text-zinc-200">{rec}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Per-Creator Table */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
          5. Per-Creator Results Table
        </h2>

        <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-900/80 border-b border-white/10 text-zinc-400 font-semibold">
                <tr>
                  <th className="p-3.5">Creator</th>
                  <th className="p-3.5 text-center">Rated</th>
                  <th className="p-3.5 text-center">Post As-Is</th>
                  <th className="p-3.5 text-center">With Edits</th>
                  <th className="p-3.5 text-center">No</th>
                  <th className="p-3.5 text-center">Postable</th>
                  <th className="p-3.5 text-right">WTP (Open)</th>
                  <th className="p-3.5 text-center">₹1.5k?</th>
                  <th className="p-3.5 text-center">Next Upload</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-zinc-300">
                {report.creator_summaries.map((cs) => (
                  <tr key={cs.creator_name} className="hover:bg-white/5">
                    <td className="p-3.5 font-bold text-white">{cs.creator_name}</td>
                    <td className="p-3.5 text-center font-mono">{cs.clips_rated}</td>
                    <td className="p-3.5 text-center font-mono text-emerald-400">{cs.post_as_is_pct}%</td>
                    <td className="p-3.5 text-center font-mono text-amber-400">{cs.post_with_edits_pct}%</td>
                    <td className="p-3.5 text-center font-mono text-rose-400">{cs.no_pct}%</td>
                    <td className="p-3.5 text-center font-mono font-bold text-white">
                      {cs.postable_clips_count}
                    </td>
                    <td className="p-3.5 text-right font-mono text-purple-300">
                      {cs.price_open_inr ? `₹${cs.price_open_inr.toLocaleString()}` : "—"}
                    </td>
                    <td className="p-3.5 text-center">
                      {cs.accepts_1500 === true ? (
                        <span className="text-emerald-400 font-bold">Yes</span>
                      ) : cs.accepts_1500 === false ? (
                        <span className="text-rose-400">No</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="p-3.5 text-center capitalize">{cs.would_upload_next || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
