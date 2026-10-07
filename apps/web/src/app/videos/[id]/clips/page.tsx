"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Video, Job } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { VideoPlayer, VideoPlayerRef } from "@/components/VideoPlayer";
import { ClipsDeck } from "@/components/ClipsDeck";
import { ArrowLeft, Film, Loader2 } from "lucide-react";

export default function VideoClipsDirectPage() {
  const params = useParams();
  const videoId = params.id as string;

  const [video, setVideo] = useState<Video | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [proxyUrl, setProxyUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const playerRef = useRef<VideoPlayerRef | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const videoData = await api.getVideo(videoId);
        setVideo(videoData);

        const proxyRes = await api.getProxyUrl(videoId).catch(() => null);
        if (proxyRes?.proxy_url) {
          setProxyUrl(proxyRes.proxy_url);
        }

        const directJob = await api.getJob(videoData.id).catch(() => null);
        if (directJob) setJob(directJob);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    if (videoId) loadData();
  }, [videoId]);

  const handleSeek = (startMs: number, endMs: number) => {
    if (playerRef.current) {
      playerRef.current.seek(startMs / 1000.0);
      playerRef.current.play();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  if (!video) {
    return (
      <div className="p-8 text-center text-zinc-400">
        <p>Video not found</p>
        <Link href="/dashboard" className="text-purple-400 underline text-sm mt-2 inline-block">
          Return to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href={`/videos/${videoId}`}
          className="inline-flex items-center gap-2 text-xs font-medium text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Video
        </Link>
        <h1 className="text-lg font-bold text-white truncate">{video.original_filename} &bull; Clips</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-5 space-y-4 lg:sticky lg:top-6">
          <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
            <Film className="w-4 h-4 text-purple-400" /> Video Preview (720p Proxy)
          </h2>
          <VideoPlayer
            ref={playerRef}
            src={proxyUrl || ""}
            poster=""
            title={video.original_filename}
          />
        </div>

        <div className="lg:col-span-7">
          <ClipsDeck
            videoId={videoId}
            proxyUrl={proxyUrl}
            onSeek={handleSeek}
            isJobRunning={job?.status === "running"}
          />
        </div>
      </div>
    </div>
  );
}
