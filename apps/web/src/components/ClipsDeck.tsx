"use client";

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  ClipMoment,
  Clip,
  VideoClipsResponse,
  FeedbackReasonTag,
  ClipScoredEventPayload,
} from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { ClipCard } from "./ClipCard";
import {
  Download,
  Trash2,
  Sparkles,
  Layers,
  ArrowUpDown,
  Filter,
  RefreshCw,
  CheckSquare,
  Square,
  AlertCircle,
} from "lucide-react";

interface ClipsDeckProps {
  videoId: string;
  proxyUrl?: string | null;
  onSeek: (startMs: number, endMs: number) => void;
  isJobRunning?: boolean;
}

export const ClipsDeck: React.FC<ClipsDeckProps> = ({
  videoId,
  proxyUrl,
  onSeek,
  isJobRunning,
}) => {
  const [moments, setMoments] = useState<ClipMoment[]>([]);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const pendingMomentsRef = useRef<ClipMoment[]>([]);

  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"score" | "time" | "rank">("score");
  const [minScore, setMinScore] = useState<number>(0);
  const [isRescoring, setIsRescoring] = useState(false);
  const [streamingNotice, setStreamingNotice] = useState<string | null>(null);

  // Bulk selection
  const [selectedClipIds, setSelectedClipIds] = useState<Set<string>>(new Set());
  const [isBulkProcessing, setIsBulkProcessing] = useState(false);

  const fetchClips = useCallback(async (isInitial = false) => {
    try {
      const res = await api.getVideoClips(videoId, { sort: sortBy });
      const fetchedMoments = res.moments || [];

      if (isInitial || moments.length === 0) {
        setMoments(fetchedMoments);
        setPendingCount(0);
      } else {
        // Compare with current moments
        const currentIds = new Set(moments.map((m) => m.id));
        const newOnes = fetchedMoments.filter((m) => !currentIds.has(m.id));
        if (newOnes.length > 0) {
          pendingMomentsRef.current = fetchedMoments;
          setPendingCount(newOnes.length);
        } else {
          setMoments(fetchedMoments);
        }
      }
    } catch (err) {
      console.error("Failed to fetch clips:", err);
    } finally {
      setLoading(false);
    }
  }, [videoId, sortBy, moments]);

  useEffect(() => {
    fetchClips(true);
  }, [fetchClips]);

  // Merge pending streamed clips without shifting layout unexpectedly
  const handleMergeNewClips = () => {
    if (pendingMomentsRef.current.length > 0) {
      setMoments(pendingMomentsRef.current);
      pendingMomentsRef.current = [];
      setPendingCount(0);
    }
  };

  // SSE clip_scored listener
  useEffect(() => {
    if (!videoId) return;
    const sseUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/jobs/stream?video_id=${videoId}`;
    let eventSource: EventSource | null = null;

    try {
      eventSource = new EventSource(sseUrl);
      eventSource.addEventListener("clip_scored", (e: any) => {
        try {
          const payload = JSON.parse(e.data);
          setStreamingNotice(
            `Scored ${payload.scored_count || ""} clips... analyzing virality`
          );
          fetchClips(false);
        } catch {}
      });
    } catch {}

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [videoId, fetchClips]);

  const handleFeedback = async (
    clipId: string,
    value: "up" | "down",
    reasonTag?: FeedbackReasonTag
  ) => {
    try {
      await api.submitClipFeedback(clipId, { value, reason_tag: reasonTag });
      fetchClips(false);
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    }
  };

  const handleDeleteFeedback = async (clipId: string) => {
    try {
      await api.deleteClipFeedback(clipId);
      fetchClips(false);
    } catch (err) {
      console.error("Failed to delete feedback:", err);
    }
  };

  const handleRescore = async () => {
    setIsRescoring(true);
    try {
      await api.rescoreVideo(videoId);
      setStreamingNotice("Rescoring enqueued... Analyzing viral hooks.");
    } catch (err) {
      console.error("Failed to trigger rescore:", err);
    } finally {
      setIsRescoring(false);
    }
  };

  const handleToggleSelect = (clipId: string) => {
    setSelectedClipIds((prev) => {
      const next = new Set(prev);
      if (next.has(clipId)) {
        next.delete(clipId);
      } else {
        next.add(clipId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    const allClipIds = new Set(
      moments.flatMap((m) => m.clips.map((c) => c.id))
    );
    setSelectedClipIds(allClipIds);
  };

  const handleClearSelection = () => {
    setSelectedClipIds(new Set());
  };

  const handleBulkExport = async () => {
    if (selectedClipIds.size === 0) return;
    try {
      setIsBulkProcessing(true);
      await api.bulkClipActions({
        action: "export",
        clip_ids: Array.from(selectedClipIds),
        preset: "tiktok",
      });
      setSelectedClipIds(new Set());
    } catch (err) {
      console.error("Bulk export failed", err);
    } finally {
      setIsBulkProcessing(false);
    }
  };

  const handleBulkDismiss = async () => {
    if (selectedClipIds.size === 0) return;
    try {
      setIsBulkProcessing(true);
      await api.bulkClipActions({
        action: "dismiss",
        clip_ids: Array.from(selectedClipIds),
      });
      setSelectedClipIds(new Set());
      fetchClips(true);
    } catch (err) {
      console.error("Bulk dismiss failed", err);
    } finally {
      setIsBulkProcessing(false);
    }
  };

  const filteredMoments = useMemo(() => {
    return moments.filter((m) => {
      if (filterStatus !== "all" && m.status !== filterStatus) return false;
      if (minScore > 0 && (m.final_score || 0) < minScore) return false;
      return true;
    });
  }, [moments, filterStatus, minScore]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4">
        <div className="w-10 h-10 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-zinc-400 text-sm">Discovering high-retention clips...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Control Bar: Filters, Sort, Rescore, and Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-[#111420]/80 border border-white/10 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          {/* Status Filter */}
          <div className="flex items-center gap-1 bg-zinc-900/90 p-1 rounded-lg border border-white/5 text-xs">
            {["all", "selected", "scored"].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setFilterStatus(st)}
                className={`px-3 py-1 rounded capitalize font-medium transition-colors ${
                  filterStatus === st
                    ? "bg-purple-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Sort By Dropdown */}
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span>Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-zinc-900 text-zinc-200 border border-white/10 rounded-lg px-2.5 py-1 focus:outline-none focus:border-purple-500"
            >
              <option value="score">Virality Score</option>
              <option value="time">Chronological</option>
              <option value="rank">Rank Order</option>
            </select>
          </div>

          {/* Min Score Filter */}
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span>Min Score:</span>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="bg-zinc-900 text-zinc-200 border border-white/10 rounded-lg px-2.5 py-1 focus:outline-none focus:border-purple-500"
            >
              <option value={0}>All Scores</option>
              <option value={0.6}>&gt; 60%</option>
              <option value={0.75}>&gt; 75% Top Tier</option>
              <option value={0.85}>&gt; 85% Viral</option>
            </select>
          </div>
        </div>

        {/* Right side: Rescore Button & Stats */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-400 font-mono">
            {filteredMoments.length} {filteredMoments.length === 1 ? "clip" : "clips"} found
          </span>
          <button
            type="button"
            onClick={handleRescore}
            disabled={isRescoring}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md transition-transform hover:scale-102 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRescoring ? "animate-spin" : ""}`} />
            <span>{isRescoring ? "Rescoring..." : "Rescore Video"}</span>
          </button>
        </div>
      </div>

      {/* Stable Streaming Pill Banner */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between p-3 rounded-xl bg-purple-900/60 border border-purple-500/80 shadow-lg text-xs text-white animate-in slide-in-from-top-2">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
            <span className="font-semibold">
              {pendingCount} new scored clips discovered in the background!
            </span>
          </div>
          <button
            onClick={handleMergeNewClips}
            className="px-3 py-1 bg-purple-600 hover:bg-purple-500 rounded-lg text-xs font-bold transition-colors"
          >
            Merge Into Grid
          </button>
        </div>
      )}

      {/* Floating Bulk Actions Bar */}
      {selectedClipIds.size > 0 && (
        <div className="sticky top-20 z-30 p-3 bg-zinc-900/95 border border-purple-500/50 rounded-xl shadow-2xl backdrop-blur-md flex items-center justify-between gap-4 text-xs animate-in fade-in">
          <div className="flex items-center gap-2 font-bold text-white">
            <span className="bg-purple-600 px-2 py-0.5 rounded-full text-white text-[11px]">
              {selectedClipIds.size}
            </span>
            <span>Clips Selected</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleBulkExport}
              disabled={isBulkProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-lg transition-colors disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export Selected</span>
            </button>

            <button
              onClick={handleBulkDismiss}
              disabled={isBulkProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Dismiss</span>
            </button>

            <button
              onClick={handleClearSelection}
              className="text-zinc-400 hover:text-white px-2 py-1"
            >
              Deselect All
            </button>
          </div>
        </div>
      )}

      {/* Streaming Notice while background job runs */}
      {(isJobRunning || streamingNotice) && (
        <div className="flex items-center gap-3 p-3.5 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200">
          <div className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
          <span>
            {streamingNotice || "Pipeline running: Analyzing audio acoustics & scoring viral hooks..."}
          </span>
        </div>
      )}

      {/* Empty State */}
      {filteredMoments.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-2xl bg-[#111420]/40 border border-white/5 text-center space-y-3">
          <div className="p-4 rounded-full bg-purple-600/10 text-purple-400 border border-purple-500/20">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h4 className="text-zinc-200 font-semibold">No clips found matching your filters</h4>
          <p className="text-zinc-400 text-xs max-w-sm">
            Try adjusting your score filter or click &quot;Rescore Video&quot; to recalculate clips with updated model weights.
          </p>
        </div>
      ) : (
        /* Clips Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredMoments.map((moment) => {
            const isAnySelected = moment.clips.some((c) => selectedClipIds.has(c.id));
            return (
              <ClipCard
                key={moment.id}
                moment={moment}
                proxyUrl={proxyUrl}
                onSeek={onSeek}
                onFeedback={handleFeedback}
                onDeleteFeedback={handleDeleteFeedback}
                isSelected={isAnySelected}
                onToggleSelect={handleToggleSelect}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
