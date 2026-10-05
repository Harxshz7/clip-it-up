"use client";

import { useState } from "react";
import { Job, PipelineStageName } from "@clip-it-up/shared";
import { StageStepper } from "@/components/StageStepper";
import { api } from "@/lib/api";
import {
  Activity,
  CheckCircle2,
  AlertCircle,
  Clock,
  Ban,
  RotateCcw,
  Sparkles,
} from "lucide-react";

interface JobProgressProps {
  job: Job;
  onRefresh?: () => void;
}

export function JobProgress({ job, onRefresh }: JobProgressProps) {
  const [isCancelling, setIsCancelling] = useState(false);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await api.cancelJob(job.id);
      onRefresh?.();
    } catch (err) {
      console.error("Cancel failed:", err);
    } finally {
      setIsCancelling(false);
    }
  };

  const isRunning = job.status === "running" || job.status === "queued";
  const isSucceeded = job.status === "succeeded";
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";

  return (
    <div className="space-y-6">
      {/* Overall Progress Banner */}
      <div className="glass-panel-glow rounded-3xl p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> Pipeline Job
              </span>
              <span className="text-xs text-zinc-500 font-mono">#{job.id.slice(0, 8)}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white mt-1">
              {isRunning && "Processing Video..."}
              {isSucceeded && "Video Processing Complete! ✨"}
              {isFailed && "Processing Failed"}
              {isCancelled && "Job Cancelled"}
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              {isRunning && `Executing stage: ${job.current_stage || "initializing"}...`}
              {isSucceeded && "All 6 dummy pipeline stages executed successfully with cost records."}
              {isFailed && (job.error || "An error occurred during stage execution.")}
              {isCancelled && "Processing was cancelled by user."}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {isRunning && (
              <button
                onClick={handleCancel}
                disabled={isCancelling}
                className="flex items-center gap-2 rounded-xl bg-red-500/10 px-4 py-2 text-xs font-semibold text-red-400 border border-red-500/20 hover:bg-red-500/20 active:scale-95 transition-all"
              >
                <Ban className="w-3.5 h-3.5" />
                {isCancelling ? "Cancelling..." : "Cancel Job"}
              </button>
            )}
          </div>
        </div>

        {/* Big Overall Progress Bar */}
        <div className="mt-6 space-y-2">
          <div className="flex justify-between text-xs font-medium">
            <span className="text-zinc-400">Total Progress</span>
            <span className="text-purple-400 font-bold text-sm">{job.progress}%</span>
          </div>
          <div className="w-full bg-zinc-900/80 rounded-full h-3.5 p-0.5 border border-white/10 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 relative ${
                isSucceeded
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                  : isFailed
                  ? "bg-gradient-to-r from-red-600 to-rose-500"
                  : "bg-gradient-to-r from-purple-600 via-indigo-500 to-sky-400"
              }`}
              style={{ width: `${job.progress}%` }}
            >
              {isRunning && (
                <div className="absolute inset-0 bg-white/20 animate-[pulse_1.5s_infinite]" />
              )}
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {isFailed && job.error && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-950/30 p-4 flex items-start gap-3 text-xs text-red-300">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-200">Error Details:</p>
              <p className="mt-0.5 font-mono">{job.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Stage Breakdown Grid */}
      <div>
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-purple-400" />
          Pipeline Stage Breakdown
        </h3>
        <StageStepper
          stages={job.stages}
          currentStage={job.current_stage as PipelineStageName}
        />
      </div>
    </div>
  );
}
