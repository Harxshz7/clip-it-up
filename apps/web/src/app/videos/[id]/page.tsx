"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Video, Job, JobEventPayload } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { useJobSSE } from "@/lib/sse";
import { formatBytes, formatDuration } from "@/lib/utils";
import { JobProgress } from "@/components/JobProgress";
import { VideoPlayer, VideoPlayerRef } from "@/components/VideoPlayer";
import { TranscriptViewer } from "@/components/TranscriptViewer";
import { ClipsDeck } from "@/components/ClipsDeck";
import {
  Film,
  ArrowLeft,
  Radio,
  HardDrive,
  Clock,
  Loader2,
  AlertCircle,
  FileText,
  Sparkles,
  CheckCircle2,
} from "lucide-react";

export default function VideoDetailPage() {
  const params = useParams();
  const videoId = params.id as string;

  const [video, setVideo] = useState<Video | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [proxyUrl, setProxyUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"clips" | "transcript">("clips");

  // Playback sync state between VideoPlayer and TranscriptViewer
  const [currentPlaybackMs, setCurrentPlaybackMs] = useState(0);
  const playerRef = useRef<VideoPlayerRef | null>(null);

  // Initial fetch for video and associated active/latest job
  const fetchVideoAndJob = useCallback(async () => {
    try {
      setLoading(true);
      const videoData = await api.getVideo(videoId);
      setVideo(videoData);

      // Check if job exists in complete response or query
      const jobList = (videoData as any).jobs as Job[] | undefined;
      if (jobList && jobList.length > 0) {
        setJob(jobList[0]);
      } else {
        const directJob = await api.getJob(videoData.id).catch(() => null);
        if (directJob) setJob(directJob);
      }

      // Fetch preview proxy URL if proxy_key exists or video is processed/ready
      if (videoData.proxy_key || videoData.status === "ready" || videoData.status === "processing") {
        try {
          const proxyRes = await api.getProxyUrl(videoId);
          if (proxyRes?.proxy_url) {
            setProxyUrl(proxyRes.proxy_url);
          }
        } catch (proxyErr) {
          console.log("Proxy URL not ready yet:", proxyErr);
        }
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load video details");
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    if (videoId) {
      fetchVideoAndJob();
    }
  }, [videoId, fetchVideoAndJob]);

  // Hook into SSE stream for realtime pipeline & stage updates
  const { isConnected } = useJobSSE({
    jobId: job?.id || "",
    enabled: Boolean(job?.id),
    onEvent: (payload: JobEventPayload) => {
      setJob((prev) => {
        if (!prev) {
          return {
            id: payload.job_id,
            video_id: payload.video_id || videoId,
            user_id: payload.user_id || "",
            status: payload.status,
            current_stage: payload.current_stage,
            progress: payload.progress,
            error: payload.error,
            partial_results: payload.partial_results,
            stages: payload.stages,
            created_at: payload.timestamp,
          } as Job;
        }

        return {
          ...prev,
          status: payload.status,
          current_stage: payload.current_stage,
          progress: payload.progress,
          error: payload.error,
          partial_results: payload.partial_results || prev.partial_results,
          stages: payload.stages,
        };
      });

      // When transcript or proxy becomes ready in partial_results or proxy stage succeeds, fetch proxy URL
      if (payload.partial_results?.transcript || payload.stages?.some(s => s.name === "proxy" && s.status === "succeeded")) {
        if (!proxyUrl) {
          api.getProxyUrl(videoId).then(res => {
            if (res?.proxy_url) setProxyUrl(res.proxy_url);
          }).catch(() => {});
        }
      }

      // Also update video status
      if (payload.status === "succeeded") {
        setVideo((v) => (v ? { ...v, status: "ready" } : v));
      } else if (payload.status === "failed") {
        setVideo((v) => (v ? { ...v, status: "failed" } : v));
      }
    },
  });

  // Determine if transcript is ready to show
  const isTranscriptReady =
    Boolean(job?.partial_results?.transcript) ||
    Boolean(video?.proxy_key) ||
    video?.status === "ready" ||
    job?.status === "succeeded";

  const isTranscribing =
    job?.current_stage === "transcribe" ||
    job?.current_stage === "ingest" ||
    job?.current_stage === "proxy";

  const handleSeek = (seconds: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds);
    }
  };

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
        <p className="text-xs text-zinc-400">
          {error || "The requested video does not exist or you do not have permission to view it."}
        </p>
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
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Navigation & Live SSE Status Badge */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <div className="flex items-center gap-2">
          {isTranscriptReady && job?.status === "running" && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
              <Sparkles className="w-3 h-3 text-purple-400 animate-pulse" />
              Transcript Ready (Pipeline continuing)
            </span>
          )}

          {isConnected ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Live SSE Connected
            </span>
          ) : job?.status === "succeeded" ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" /> Pipeline Completed
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
                {formatDuration(video.duration_seconds || 0)}
              </span>
              {video.width && video.height && (
                <>
                  <span>•</span>
                  <span className="text-zinc-500">
                    {video.width}x{video.height} @ {video.fps ? `${Math.round(video.fps)}fps` : ""}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area: Side-by-Side Video Player & Clips / Transcript Viewers */}
      <div className="space-y-6">
        {/* Tab Switcher */}
        <div className="flex items-center gap-2 border-b border-white/10 pb-3">
          <button
            type="button"
            onClick={() => setActiveTab("clips")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "clips"
                ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
            }`}
          >
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>AI Clips & Moments</span>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-white/20 text-white font-mono">
              Phase 2
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("transcript")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              activeTab === "transcript"
                ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Transcript & Speakers</span>
          </button>
        </div>

        {/* Video Player & Active Tab Content */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Video Player */}
          <div className="lg:col-span-6 space-y-4 lg:sticky lg:top-6">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
                <Film className="w-4 h-4 text-purple-400" /> Video Preview (720p Proxy)
              </h2>
              <span className="text-[11px] text-zinc-500">
                Shortcuts: Space (Play/Pause), J/L (Seek)
              </span>
            </div>

            <VideoPlayer
              ref={playerRef}
              src={proxyUrl || ""}
              poster=""
              title={video.original_filename}
              onTimeUpdate={(ms) => setCurrentPlaybackMs(ms)}
            />

            {!proxyUrl && (
              <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-white/5 text-xs text-zinc-400 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                <span>Generating optimized 720p preview proxy in the background...</span>
              </div>
            )}
          </div>

          {/* Right Column: Dynamic Tab Content */}
          <div className="lg:col-span-6 space-y-4">
            {activeTab === "clips" ? (
              <ClipsDeck
                videoId={videoId}
                proxyUrl={proxyUrl}
                onSeek={handleSeek}
                isJobRunning={job?.status === "running"}
              />
            ) : (
              <TranscriptViewer
                videoId={videoId}
                currentMs={currentPlaybackMs}
                onSeek={handleSeek}
                isTranscribing={isTranscribing && !isTranscriptReady}
                transcribeProgress={job?.progress || 0}
                error={job?.error}
                onRetry={fetchVideoAndJob}
              />
            )}
          </div>
        </div>
      </div>

      {/* Bottom Area: Pipeline Job Progress Stepper */}
      {job && (
        <div className="mt-8 pt-6 border-t border-white/5">
          <JobProgress job={job} onRefresh={fetchVideoAndJob} />
        </div>
      )}
    </div>
  );
}
