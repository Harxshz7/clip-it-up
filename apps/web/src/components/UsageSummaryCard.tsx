"use client";

import { useEffect, useState } from "react";
import { UsageSummary } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { Coins, HardDrive, Cpu, MessageSquare, Video, RefreshCw } from "lucide-react";

export function UsageSummaryCard() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      const data = await api.getUsageSummary();
      setSummary(data);
    } catch (err) {
      console.warn("Could not fetch usage summary:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const getMetricIcon = (metric: string) => {
    switch (metric) {
      case "source_minutes":
      case "audio_minutes":
        return <Video className="w-4 h-4 text-sky-400" />;
      case "cpu_seconds":
      case "gpu_seconds":
        return <Cpu className="w-4 h-4 text-purple-400" />;
      case "llm_tokens":
        return <MessageSquare className="w-4 h-4 text-emerald-400" />;
      default:
        return <HardDrive className="w-4 h-4 text-amber-400" />;
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 sm:p-6">
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
            <Coins className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Monthly Usage & Cost</h3>
            <p className="text-xs text-zinc-400">Current Month: {summary?.month || "Loading..."}</p>
          </div>
        </div>
        <button
          onClick={fetchSummary}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
          title="Refresh usage"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="mt-4 flex items-baseline justify-between">
        <span className="text-xs text-zinc-400">Total Recorded Cost:</span>
        <span className="text-xl font-bold text-white tracking-tight">
          {summary ? formatINR(summary.total_cost_inr) : "₹0.00"}
        </span>
      </div>

      <div className="mt-4 space-y-2">
        {summary?.metrics && summary.metrics.length > 0 ? (
          summary.metrics.map((m) => (
            <div
              key={m.metric}
              className="flex items-center justify-between rounded-xl bg-white/[0.02] border border-white/5 px-3 py-2 text-xs"
            >
              <div className="flex items-center gap-2">
                {getMetricIcon(m.metric)}
                <span className="font-mono text-zinc-300">{m.metric}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-zinc-400 font-mono">{Number(m.total_quantity).toLocaleString()}</span>
                <span className="font-medium text-purple-300">{formatINR(Number(m.total_cost_inr))}</span>
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-zinc-500 py-3 text-center">No stage usage recorded yet this month.</p>
        )}
      </div>
    </div>
  );
}
