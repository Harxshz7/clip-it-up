"use client";

import { JobStage, PipelineStageName } from "@clip-it-up/shared";
import { formatINR } from "@/lib/utils";
import {
  DownloadCloud,
  Film,
  FileAudio,
  Sparkles,
  TrendingUp,
  Video,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
  Ban,
} from "lucide-react";

interface StageStepperProps {
  stages?: JobStage[];
  currentStage?: PipelineStageName | null;
}

interface StageMetadata {
  key: PipelineStageName;
  label: string;
  description: string;
  icon: any;
}

const STAGES_METADATA: StageMetadata[] = [
  {
    key: "ingest",
    label: "Ingest & Validation",
    description: "S3 download, metadata verification & integrity check",
    icon: DownloadCloud,
  },
  {
    key: "proxy",
    label: "Fast Proxy",
    description: "FFmpeg 720p proxy generation for low-latency processing",
    icon: Film,
  },
  {
    key: "transcribe",
    label: "ASR Transcription",
    description: "Whisper audio speech-to-text & timestamp alignment",
    icon: FileAudio,
  },
  {
    key: "candidates",
    label: "Clip Discovery",
    description: "LLM semantic extraction of viral candidate segments",
    icon: Sparkles,
  },
  {
    key: "score",
    label: "Virality Scoring",
    description: "Hook strength, pacing, and retention scoring model",
    icon: TrendingUp,
  },
  {
    key: "render",
    label: "Render & Subtitles",
    description: "9:16 vertical crop, auto-reframe & dynamic captions",
    icon: Video,
  },
];

export function StageStepper({ stages = [], currentStage }: StageStepperProps) {
  const getStageData = (stageKey: PipelineStageName) => {
    return stages.find((s) => s.name === stageKey);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {STAGES_METADATA.map((meta, idx) => {
        const stage = getStageData(meta.key);
        const status = stage?.status || "pending";
        const progress = stage?.progress || 0;
        const duration = stage?.duration_ms ? `${(stage.duration_ms / 1000).toFixed(1)}s` : "--";
        const cost = stage?.cost_inr ? formatINR(Number(stage.cost_inr)) : "₹0.00";
        const Icon = meta.icon;

        const isRunning = status === "running";
        const isSucceeded = status === "succeeded";
        const isFailed = status === "failed";
        const isCancelled = status === "cancelled";

        return (
          <div
            key={meta.key}
            className={`rounded-2xl border p-5 transition-all relative overflow-hidden ${
              isRunning
                ? "border-purple-500/60 bg-[#151928] shadow-lg shadow-purple-500/10 ring-1 ring-purple-500/50"
                : isSucceeded
                ? "border-emerald-500/30 bg-[#0e1718]/60"
                : isFailed
                ? "border-red-500/40 bg-red-950/20"
                : isCancelled
                ? "border-zinc-800 bg-[#10131c]/60 opacity-60"
                : "border-white/5 bg-[#10131c]/60"
            }`}
          >
            {/* Top row */}
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`p-2.5 rounded-xl border ${
                    isRunning
                      ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                      : isSucceeded
                      ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400"
                      : isFailed
                      ? "bg-red-500/20 border-red-500/30 text-red-400"
                      : "bg-white/5 border-white/5 text-zinc-500"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                      Stage {idx + 1}
                    </span>
                    {isRunning && (
                      <span className="flex h-2 w-2 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500" />
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-semibold text-white">{meta.label}</h4>
                </div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center">
                {isRunning && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Running
                  </span>
                )}
                {isSucceeded && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                    <CheckCircle2 className="w-3 h-3" />
                    Done
                  </span>
                )}
                {isFailed && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/15 text-red-300 border border-red-500/30">
                    <AlertCircle className="w-3 h-3" />
                    Failed
                  </span>
                )}
                {isCancelled && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-700/30 text-zinc-400 border border-zinc-700/50">
                    <Ban className="w-3 h-3" />
                    Cancelled
                  </span>
                )}
                {status === "pending" && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800/40 text-zinc-500 border border-white/5">
                    <Clock className="w-3 h-3" />
                    Pending
                  </span>
                )}
              </div>
            </div>

            <p className="mt-2.5 text-xs text-zinc-400 leading-relaxed min-h-[32px]">{meta.description}</p>

            {/* Progress Bar */}
            <div className="mt-4 space-y-1.5">
              <div className="flex justify-between text-[11px] text-zinc-400">
                <span>Progress</span>
                <span className="font-semibold text-white">{isSucceeded ? 100 : progress}%</span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    isSucceeded
                      ? "bg-emerald-500"
                      : isFailed
                      ? "bg-red-500"
                      : "bg-gradient-to-r from-purple-500 to-indigo-500"
                  }`}
                  style={{ width: `${isSucceeded ? 100 : progress}%` }}
                />
              </div>
            </div>

            {/* Footer metrics: Duration & Stage Cost in INR */}
            <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-zinc-400">
              <span className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-zinc-500" />
                {duration}
              </span>
              <span className="font-medium text-purple-300/90 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-800/30">
                Cost: {cost}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
