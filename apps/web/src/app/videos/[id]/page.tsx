"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Video, Job, JobEventPayload } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { useJobSSE } from "@/lib/sse";
import { formatBytes, formatDuration, formatDateTime } from "@/lib/utils";
import { JobProgress } from "@/components/JobProgress";
import {
  Film,
  ArrowLeft,
  Radio,
  HardDrive,
  Clock,
  Loader2,
  AlertCircle,
  FileCode,
} from "lucide-react";

export default function VideoDetailPage() {
  const params = useParams();
  const videoId = params.id as string;

  const [video, setVideo] = useState<Video | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initial fetch for video and associated active/latest job
  const fetchVideoAndJob = async () => {
    try {
      setLoading(true);
      const videoData = await api.getVideo(videoId);
      setVideo(videoData);

      // Check if job exists in complete response or query
      const jobList = (videoData as any).jobs as Job[] | undefined;
      if (jobList && jobList.length > 0) {
        setJob(jobList[0]);
      } else {
        // Fetch job directly if video has job
        const directJob = await api.getJob(videoData.id).catch(() => null);
        if (directJob) setJob(directJob);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load video details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (videoId) {
      fetchVideoAndJob();
    }
  }, [videoId]);

  // Hook into SSE stream for realtime updates when job is available
  const { isConnected } = useJobSSE({
    jobId: job?.id || "",
    enabled: Boolean(job?.id),
    onEvent: (payload: JobEventPayload) => {
      // Merge SSE event payload directly into job state
      setJob((prev) => {
        if (!prev) {
          return {
            id: payload.job_id,
            video_id: payload.video_id,
            user_id: payload.user_id,
            status: payload.status,
            current_stage: payload.current_stage,
            progress: payload.progress,
            error: payload.error,
            created_at: payload.created_at,
            started_at: payload.started_at,
            finished_at: payload.finished_at,
            stages: payload.stages,
          } as Job;
        }

        return {
          ...prev,
          status: payload.status,
          current_stage: payload.current_stage,
          progress: payload.progress,
          error: payload.error,
          started_at: payload.started_at || prev.started_at,
          finished_at: payload.finished_at || prev.finished_at,
          stages: payload.stages,
        };
      });

      // Also update video status if finished
      if (payload.status === "succeeded") {
        setVideo((v) => (v ? { ...v, status: "ready" } : v));
      } else if (payload.status === "failed") {
        setVideo((v) => (v ? { ...v, status: "failed" } : v));
      }
    },
  });

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <p className="text-sm text-zinc-400">Loading video details & pipeline status...</p>
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="glass-panel rounded-2xl p-8 max-w-lg mx-auto text-center space-y-4">
        <div className="h-12 w-12 rounded-full bg-red-950/60 border border-red-800/40 text-red-400 flex items-center justify-center mx-auto">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-semibold text-white">Video Not Found</h2>
        <p className="text-xs text-zinc-400">{error || "The requested video does not exist or you do not have permission to view it."}</p>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-500 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Navigation & Live SSE Status Badge */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <div className="flex items-center gap-2">
          {isConnected ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Live SSE Connected
            </span>
          ) : job?.status === "succeeded" ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-300 border border-purple-500/20">
              Pipeline Completed
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-white/5">
              <Radio className="w-3 h-3" /> Standby
            </span>
          )}
        </div>
      </div>

      {/* Video Info Header Card */}
      <div className="glass-panel rounded-2xl p-5 sm:p-6 border border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-2xl bg-purple-500/15 border border-purple-500/30 text-purple-300 flex items-center justify-center shrink-0">
            <Film className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg sm:text-xl font-bold text-white truncate max-w-xl">
              {video.original_filename}
            </h1>
            <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400 mt-1">
              <span className="flex items-center gap-1">
                <HardDrive className="w-3.5 h-3.5 text-zinc-500" />
                {formatBytes(video.size_bytes)}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-zinc-500" />
                {formatDuration(video.duration_seconds)}
              </span>
              <span>•</span>
              <span className="font-mono text-[11px] text-zinc-500 truncate max-w-xs">
                {video.storage_key}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Real-time Job Progress & Stage Stepper */}
      {job ? (
        <JobProgress job={job} onRefresh={fetchVideoAndJob} />
      ) : (
        <div className="glass-panel rounded-2xl p-8 text-center space-y-3">
          <Loader2 className="w-6 h-6 animate-spin text-purple-400 mx-auto" />
          <h3 className="text-sm font-semibold text-white">Initializing Job...</h3>
          <p className="text-xs text-zinc-400">Worker pipeline is queuing the job.</p>
        </div>
      )}
    </div>
  );
}
