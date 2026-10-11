"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { EditorMetricsResponse } from "@clip-it-up/shared";
import {
  Clock,
  Sparkles,
  TrendingUp,
  BarChart3,
  Users,
  CheckCircle2,
  RefreshCw,
  ArrowLeft,
  Scissors,
  Bookmark,
  Crop,
  Layers,
  AlertTriangle,
} from "lucide-react";

export default function AdminEditorMetricsPage() {
  const [metrics, setMetrics] = useState<EditorMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getEditorMetrics();
      setMetrics(res);
    } catch (err: any) {
      setError(err?.message || "Failed to load editor metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const formatSeconds = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = Math.round(s % 60);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-black text-white flex items-center gap-2.5">
            <BarChart3 className="w-6 h-6 text-purple-400" />
            Studio Editor Telemetry &amp; 5-Minute Goal
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Real-time analytics measuring speed of workflow, hands-on time, and edit drop-offs.
          </p>
        </div>

        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl text-xs font-bold transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Data</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-700/50 text-red-200 text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && !metrics ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <div className="w-8 h-8 rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
        </div>
      ) : metrics ? (
        <div className="space-y-8">
          {/* Top Key Metric Cards: 5-Minute Goal Tracking */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Median Hands-on Time */}
            <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs">
                <span className="font-semibold uppercase tracking-wider">Median Hands-On Time</span>
                <Clock className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-black text-white">
                {formatSeconds(metrics.median_hands_on_time_s)}
              </div>
              <div className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Goal &le; 5 min met ({metrics.median_hands_on_time_s.toFixed(0)}s)</span>
              </div>
            </div>

            {/* P90 Hands-on Time */}
            <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs">
                <span className="font-semibold uppercase tracking-wider">P90 Hands-On Time</span>
                <TrendingUp className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-3xl font-black text-white">
                {formatSeconds(metrics.p90_hands_on_time_s)}
              </div>
              <div className="text-[11px] text-zinc-400 font-mono">
                90% of sessions finish under {metrics.p90_hands_on_time_s.toFixed(0)}s
              </div>
            </div>

            {/* Time to First Clip */}
            <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs">
                <span className="font-semibold uppercase tracking-wider">Time to 1st Clip</span>
                <Sparkles className="w-4 h-4 text-yellow-400" />
              </div>
              <div className="text-3xl font-black text-white">
                {formatSeconds(metrics.median_time_to_first_clip_s)}
              </div>
              <div className="text-[11px] text-zinc-400 font-mono">
                Streaming progressive preview
              </div>
            </div>

            {/* Export Without Editing Rate */}
            <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 shadow-xl space-y-2">
              <div className="flex items-center justify-between text-zinc-400 text-xs">
                <span className="font-semibold uppercase tracking-wider">Ready Out-Of-Box</span>
                <CheckCircle2 className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-3xl font-black text-white">
                {Math.round(metrics.export_without_editing_rate * 100)}%
              </div>
              <div className="text-[11px] text-zinc-400 font-mono">
                Exported with 0 manual edits
              </div>
            </div>
          </div>

          {/* Secondary Details: Edit Type Frequencies & Drop-off Funnel */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Edit Action Breakdown (col-span-7) */}
            <div className="lg:col-span-7 p-6 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4 shadow-xl">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <Scissors className="w-4 h-4 text-purple-400" />
                Edit Action Frequencies
              </h3>
              <p className="text-xs text-zinc-400">
                Most common user interactions across active editing sessions.
              </p>

              <div className="space-y-3 pt-2">
                {Object.entries(metrics.edit_type_frequencies || {}).length === 0 ? (
                  <p className="text-zinc-500 text-xs">No edit actions recorded yet.</p>
                ) : (
                  Object.entries(metrics.edit_type_frequencies).map(([type, count]) => (
                    <div key={type} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="capitalize font-medium text-zinc-300">
                          {type.replace(/_/g, " ")}
                        </span>
                        <span className="font-mono text-zinc-400">{count} actions</span>
                      </div>
                      <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full bg-purple-500 rounded-full"
                          style={{
                            width: `${Math.min(100, Math.max(10, count * 15))}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right: Funnel & Drop-off Points (col-span-5) */}
            <div className="lg:col-span-5 p-6 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4 shadow-xl">
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                Workflow Drop-off Funnel
              </h3>
              <p className="text-xs text-zinc-400">
                Stage progression from video upload to completed export.
              </p>

              <div className="space-y-3 pt-2 font-mono text-xs">
                <div className="p-3 rounded-xl bg-purple-950/40 border border-purple-700/50 flex items-center justify-between">
                  <span className="text-purple-200">Export Completed</span>
                  <span className="font-bold text-white">
                    {metrics.drop_off_points?.completed_export || 0}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-zinc-800/80 border border-zinc-700 flex items-center justify-between">
                  <span className="text-zinc-300">Edited but No Export</span>
                  <span className="font-bold text-zinc-400">
                    {metrics.drop_off_points?.edit_no_export || 0}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-zinc-800/40 border border-zinc-700/60 flex items-center justify-between">
                  <span className="text-zinc-400">Opened but No Edit</span>
                  <span className="font-bold text-zinc-500">
                    {metrics.drop_off_points?.open_no_edit || 0}
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-zinc-800 text-[11px] text-zinc-400 flex justify-between">
                <span>Total Recorded Sessions:</span>
                <span className="font-bold text-white">{metrics.total_sessions}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
