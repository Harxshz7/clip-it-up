"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Video } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { formatBytes, formatDuration, formatDateTime } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { UsageSummaryCard } from "@/components/UsageSummaryCard";
import { OnboardingChecklist } from "@/components/OnboardingChecklist";
import {
  Film,
  Upload,
  RefreshCw,
  Clock,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  HardDrive,
  Play,
  Sparkles,
} from "lucide-react";

export default function DashboardPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const setUploadModalOpen = useAppStore((s) => s.setUploadModalOpen);

  const fetchVideos = async () => {
    try {
      setLoading(true);
      const data = await api.getVideos();
      setVideos(data);
    } catch (err) {
      console.error("Failed to fetch videos:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVideos();
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ready":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Ready
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20">
            <Loader2 className="w-3 h-3 animate-spin" /> Processing
          </span>
        );
      case "uploaded":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-500/10 text-sky-300 border border-sky-500/20">
            <Clock className="w-3 h-3" /> Uploaded
          </span>
        );
      case "uploading":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20">
            <Loader2 className="w-3 h-3 animate-spin" /> Uploading
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-300 border border-red-500/20">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      default:
        return <span className="text-xs text-zinc-500">{status}</span>;
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Videos & Jobs</h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            Manage your uploaded source videos and monitor pipeline processing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchVideos}
            className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={() => setUploadModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 transition-all"
          >
            <Upload className="w-3.5 h-3.5" />
            Upload Video
          </button>
        </div>
      </div>

      {/* Onboarding Quickstart Checklist */}
      <OnboardingChecklist hasUploadedVideos={videos.length > 0} />

      {/* Grid: Main Video List + Side Usage Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Videos List (2 Columns) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
              <Film className="w-4 h-4 text-purple-400" />
              Source Videos ({videos.length})
            </h2>

            <Link
              href="/videos/00000000-0000-0000-0000-000000000099/clips"
              className="text-xs font-semibold text-purple-400 hover:text-purple-300 flex items-center gap-1.5 transition-colors"
            >
              <Play className="w-3 h-3 fill-purple-400 text-purple-400" />
              <span>Open Sample Demo</span>
            </Link>
          </div>

          {loading && videos.length === 0 && (
            <div className="flex items-center justify-center p-12 glass-panel rounded-2xl">
              <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
            </div>
          )}

          {!loading && videos.length === 0 && (
            <div className="glass-panel rounded-2xl p-8 text-center space-y-5">
              <div className="h-12 w-12 rounded-2xl bg-purple-950/60 border border-purple-800/40 text-purple-400 flex items-center justify-center mx-auto">
                <Film className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">No videos uploaded yet</h3>
                <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto leading-relaxed">
                  Upload your first video to run our 6-stage clipping pipeline, or explore our precomputed sample project with zero quota usage.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <Link
                  href="/videos/00000000-0000-0000-0000-000000000099/clips"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 transition-all"
                >
                  <Play className="w-3.5 h-3.5 fill-white text-white" />
                  Try Sample Project (Zero Quota)
                </Link>

                <button
                  onClick={() => setUploadModalOpen(true)}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-2.5 text-xs font-semibold text-zinc-300 hover:text-white hover:bg-white/10 transition-all"
                >
                  <Upload className="w-3.5 h-3.5 text-purple-400" /> Upload Your Video
                </button>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {videos.map((vid) => (
              <Link
                key={vid.id}
                href={`/videos/${vid.id}`}
                className="block glass-panel rounded-2xl p-4 sm:p-5 hover:border-purple-500/40 hover:bg-white/[0.04] transition-all group"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="h-10 w-10 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                      <Film className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-sm font-semibold text-white truncate group-hover:text-purple-300 transition-colors">
                        {vid.original_filename}
                      </h4>
                      <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1">
                        <span>{formatBytes(vid.size_bytes)}</span>
                        <span>•</span>
                        <span>{formatDuration(vid.duration_seconds)}</span>
                        <span>•</span>
                        <span>{formatDateTime(vid.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {getStatusBadge(vid.status)}
                    <ArrowRight className="w-4 h-4 text-zinc-500 group-hover:text-purple-300 group-hover:translate-x-0.5 transition-all" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Usage & Cost Summary (1 Column) */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-purple-400" />
            Billing & Usage
          </h2>
          <UsageSummaryCard />
        </div>
      </div>
    </div>
  );
}
