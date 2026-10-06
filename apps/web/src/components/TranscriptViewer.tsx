"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import {
  TranscriptResponse,
  TranscriptSegment,
  TranscriptWord,
  Speaker,
  ExportFormat,
} from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import {
  Search,
  Download,
  Edit2,
  Check,
  X,
  ChevronUp,
  ChevronDown,
  ArrowDown,
  FileText,
  Clock,
  Sparkles,
  AlertCircle,
  Loader2,
  RefreshCw,
} from "lucide-react";

interface TranscriptViewerProps {
  videoId: string;
  currentMs: number;
  onSeek: (seconds: number) => void;
  isTranscribing?: boolean;
  transcribeProgress?: number;
  error?: string | null;
  onRetry?: () => void;
}

const SPEAKER_COLORS = [
  { bg: "bg-purple-500/15", border: "border-purple-500/30", text: "text-purple-300", badge: "bg-purple-500/20 text-purple-300 border-purple-500/40" },
  { bg: "bg-emerald-500/15", border: "border-emerald-500/30", text: "text-emerald-300", badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" },
  { bg: "bg-sky-500/15", border: "border-sky-500/30", text: "text-sky-300", badge: "bg-sky-500/20 text-sky-300 border-sky-500/40" },
  { bg: "bg-amber-500/15", border: "border-amber-500/30", text: "text-amber-300", badge: "bg-amber-500/20 text-amber-300 border-amber-500/40" },
  { bg: "bg-rose-500/15", border: "border-rose-500/30", text: "text-rose-300", badge: "bg-rose-500/20 text-rose-300 border-rose-500/40" },
  { bg: "bg-indigo-500/15", border: "border-indigo-500/30", text: "text-indigo-300", badge: "bg-indigo-500/20 text-indigo-300 border-indigo-500/40" },
];

export function TranscriptViewer({
  videoId,
  currentMs,
  onSeek,
  isTranscribing = false,
  transcribeProgress = 0,
  error = null,
  onRetry,
}: TranscriptViewerProps) {
  const [data, setData] = useState<TranscriptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Speaker editing state
  const [editingSpeakerId, setEditingSpeakerId] = useState<string | null>(null);
  const [editingSpeakerName, setEditingSpeakerName] = useState("");
  const [isSavingSpeaker, setIsSavingSpeaker] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [activeMatchIndex, setActiveMatchIndex] = useState(0);

  // Auto-scroll state
  const [autoScroll, setAutoScroll] = useState(true);
  const [userHasScrolled, setUserHasScrolled] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const activeWordRef = useRef<HTMLSpanElement | null>(null);

  // Export menu state
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Fetch initial transcript data
  const loadTranscript = useCallback(async () => {
    try {
      setLoading(true);
      setFetchError(null);
      const res = await api.getTranscript(videoId);
      setData(res);
    } catch (err: any) {
      if (err?.code !== "HTTP_404") {
        setFetchError(err?.message || "Failed to load transcript");
      } else {
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [videoId]);

  useEffect(() => {
    if (videoId) {
      loadTranscript();
    }
  }, [videoId, loadTranscript]);

  // Map speaker label -> Speaker object & styling index
  const speakerMap = useMemo(() => {
    const map = new Map<string, { speaker: Speaker; styleIndex: number }>();
    if (data?.speakers) {
      data.speakers.forEach((s, idx) => {
        map.set(s.label, { speaker: s, styleIndex: idx % SPEAKER_COLORS.length });
      });
    }
    return map;
  }, [data?.speakers]);

  // Search matches calculation
  const searchMatches = useMemo(() => {
    if (!searchQuery.trim() || !data?.segments) return [];
    const query = searchQuery.toLowerCase();
    const matches: { segmentIdx: number; wordIdx?: number; elementId: string }[] = [];

    data.segments.forEach((seg, sIdx) => {
      if (seg.words && seg.words.length > 0) {
        seg.words.forEach((w, wIdx) => {
          if (w.word.toLowerCase().includes(query)) {
            matches.push({ segmentIdx: sIdx, wordIdx: wIdx, elementId: `word-${w.id}` });
          }
        });
      } else if (seg.text.toLowerCase().includes(query)) {
        matches.push({ segmentIdx: sIdx, elementId: `seg-${seg.id}` });
      }
    });

    return matches;
  }, [searchQuery, data?.segments]);

  // Navigate search matches
  const handleNextMatch = () => {
    if (searchMatches.length === 0) return;
    const nextIdx = (activeMatchIndex + 1) % searchMatches.length;
    setActiveMatchIndex(nextIdx);
    scrollToMatch(nextIdx);
  };

  const handlePrevMatch = () => {
    if (searchMatches.length === 0) return;
    const prevIdx = (activeMatchIndex - 1 + searchMatches.length) % searchMatches.length;
    setActiveMatchIndex(prevIdx);
    scrollToMatch(prevIdx);
  };

  const scrollToMatch = (idx: number) => {
    const match = searchMatches[idx];
    if (match) {
      const el = document.getElementById(match.elementId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  };

  // Find active word and segment based on current playback ms
  const activeWordId = useMemo(() => {
    if (!data?.segments) return null;
    for (const seg of data.segments) {
      if (currentMs >= seg.start_ms && currentMs <= seg.end_ms) {
        if (seg.words) {
          const match = seg.words.find(
            (w) => currentMs >= w.start_ms && currentMs <= w.end_ms
          );
          if (match) return match.id;
        }
      }
    }
    return null;
  }, [data?.segments, currentMs]);

  // Handle user scroll detection
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    // If user interacts with scrollbar
    if (autoScroll) {
      setAutoScroll(false);
      setUserHasScrolled(true);
    }
  };

  // Auto-scroll when active word changes
  useEffect(() => {
    if (autoScroll && activeWordRef.current) {
      activeWordRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "nearest",
      });
    }
  }, [activeWordId, autoScroll]);

  // Resume auto-scroll
  const handleResumeAutoScroll = () => {
    setAutoScroll(true);
    setUserHasScrolled(false);
    if (activeWordRef.current) {
      activeWordRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  };

  // Speaker name edit submission
  const handleSaveSpeaker = async (speaker: Speaker) => {
    if (!editingSpeakerName.trim() || editingSpeakerName === (speaker.display_name || speaker.label)) {
      setEditingSpeakerId(null);
      return;
    }

    try {
      setIsSavingSpeaker(true);
      const updated = await api.updateSpeaker(videoId, speaker.id, editingSpeakerName.trim());
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          speakers: prev.speakers.map((s) => (s.id === updated.id ? updated : s)),
        };
      });
      setEditingSpeakerId(null);
    } catch (err) {
      console.error("Failed to update speaker name:", err);
    } finally {
      setIsSavingSpeaker(false);
    }
  };

  // Handle export download
  const handleExport = async (format: ExportFormat) => {
    try {
      setIsExporting(true);
      setShowExportMenu(false);
      const content = await api.exportTranscriptText(videoId, format);
      const blob = new Blob([content], {
        type: format === "json" ? "application/json" : "text/plain;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transcript_${videoId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  // 1. Transcribing / Processing State
  if (isTranscribing && !data?.segments?.length) {
    return (
      <div className="glass-panel rounded-2xl p-8 h-[540px] flex flex-col items-center justify-center text-center space-y-4 border border-purple-500/20">
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Sparkles className="w-8 h-8 animate-pulse" />
          </div>
          <Loader2 className="w-6 h-6 animate-spin text-purple-400 absolute -top-1 -right-1" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white">Transcribing Audio with WhisperX...</h3>
          <p className="text-xs text-zinc-400 mt-1 max-w-sm">
            Running batched transcription, wav2vec2 word alignment, and pyannote speaker diarization.
          </p>
        </div>
        <div className="w-48 bg-zinc-900 rounded-full h-2 overflow-hidden border border-white/10">
          <div
            className="bg-gradient-to-r from-purple-600 to-sky-400 h-full transition-all duration-300"
            style={{ width: `${transcribeProgress || 30}%` }}
          />
        </div>
      </div>
    );
  }

  // 2. Failed State
  if (error || fetchError) {
    return (
      <div className="glass-panel rounded-2xl p-8 h-[540px] flex flex-col items-center justify-center text-center space-y-4 border border-red-500/20">
        <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400">
          <AlertCircle className="w-7 h-7" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white">Transcription Unavailable</h3>
          <p className="text-xs text-red-300 mt-1 max-w-sm font-mono">
            {error || fetchError || "Unable to load transcript."}
          </p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-500 active:scale-95 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Retry Processing
          </button>
        )}
      </div>
    );
  }

  // 3. Loading State
  if (loading && !data) {
    return (
      <div className="glass-panel rounded-2xl p-8 h-[540px] flex flex-col items-center justify-center text-center space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <p className="text-xs text-zinc-400">Loading transcript...</p>
      </div>
    );
  }

  // 4. Empty State
  if (!data || !data.segments || data.segments.length === 0) {
    return (
      <div className="glass-panel rounded-2xl p-8 h-[540px] flex flex-col items-center justify-center text-center space-y-3 border border-white/5">
        <FileText className="w-10 h-10 text-zinc-600" />
        <h3 className="text-sm font-semibold text-zinc-300">No Transcript Available</h3>
        <p className="text-xs text-zinc-500 max-w-xs">
          This video does not have a transcript yet or processing hasn't started.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl flex flex-col h-[560px] border border-white/10 overflow-hidden shadow-2xl relative">
      {/* Top Action Header: Search & Export */}
      <div className="p-3.5 border-b border-white/10 bg-zinc-950/40 flex items-center justify-between gap-3 shrink-0">
        {/* Search Bar */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search transcript..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setActiveMatchIndex(0);
            }}
            className="w-full bg-zinc-900/90 border border-white/10 rounded-xl pl-8 pr-20 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500/50"
          />
          {searchQuery && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 text-[11px] text-zinc-400">
              <span>
                {searchMatches.length > 0 ? `${activeMatchIndex + 1}/${searchMatches.length}` : "0"}
              </span>
              <button
                onClick={handlePrevMatch}
                disabled={searchMatches.length === 0}
                className="p-0.5 hover:text-white disabled:opacity-30"
                title="Previous match"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleNextMatch}
                disabled={searchMatches.length === 0}
                className="p-0.5 hover:text-white disabled:opacity-30"
                title="Next match"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setSearchQuery("")}
                className="p-0.5 hover:text-white ml-0.5"
                title="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>

        {/* Export Button & Menu */}
        <div className="relative">
          <button
            onClick={() => setShowExportMenu(!showExportMenu)}
            disabled={isExporting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition-colors"
          >
            {isExporting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
            ) : (
              <Download className="w-3.5 h-3.5 text-purple-400" />
            )}
            <span>Export</span>
          </button>

          {showExportMenu && (
            <div className="absolute right-0 mt-2 w-44 rounded-xl bg-zinc-900/95 border border-white/10 shadow-2xl p-1 z-30 backdrop-blur-xl">
              <div className="px-2.5 py-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                Export Format
              </div>
              {(["txt", "srt", "vtt", "json"] as ExportFormat[]).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => handleExport(fmt)}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-zinc-200 hover:bg-purple-600 hover:text-white transition-colors uppercase font-medium flex items-center justify-between"
                >
                  <span>{fmt}</span>
                  <span className="text-[10px] text-zinc-400">.{fmt}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Transcript Segments List Container */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-4 select-text"
      >
        {data.segments.map((segment: TranscriptSegment, segIdx: number) => {
          const speakerInfo = segment.speaker ? speakerMap.get(segment.speaker) : null;
          const color = speakerInfo
            ? SPEAKER_COLORS[speakerInfo.styleIndex]
            : SPEAKER_COLORS[0];
          const speakerObj = speakerInfo?.speaker;
          const isSpeakerEditing = speakerObj && editingSpeakerId === speakerObj.id;

          const isSegmentActive =
            currentMs >= segment.start_ms && currentMs <= segment.end_ms;

          return (
            <div
              key={segment.id || segIdx}
              id={`seg-${segment.id}`}
              className={`p-3.5 rounded-xl border transition-all duration-200 ${
                isSegmentActive
                  ? `${color.bg} ${color.border} shadow-lg shadow-purple-950/20`
                  : "bg-white/[0.02] border-white/5 hover:border-white/15"
              }`}
            >
              {/* Segment Header: Speaker & Timestamp */}
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  {/* Speaker Label with Inline Rename */}
                  {isSpeakerEditing ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        autoFocus
                        value={editingSpeakerName}
                        onChange={(e) => setEditingSpeakerName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveSpeaker(speakerObj);
                          if (e.key === "Escape") setEditingSpeakerId(null);
                        }}
                        className="bg-zinc-800 border border-purple-500 rounded px-2 py-0.5 text-xs text-white focus:outline-none"
                      />
                      <button
                        onClick={() => handleSaveSpeaker(speakerObj)}
                        disabled={isSavingSpeaker}
                        className="p-1 text-emerald-400 hover:text-emerald-300"
                        title="Save name"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setEditingSpeakerId(null)}
                        className="p-1 text-zinc-400 hover:text-zinc-300"
                        title="Cancel"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 group">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${color.badge}`}
                      >
                        {speakerObj?.display_name || segment.speaker || "Speaker"}
                      </span>
                      {speakerObj && (
                        <button
                          onClick={() => {
                            setEditingSpeakerId(speakerObj.id);
                            setEditingSpeakerName(speakerObj.display_name || speakerObj.label);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-white transition-opacity"
                          title="Rename speaker"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Segment Start Time (Click to seek segment) */}
                <button
                  onClick={() => onSeek(segment.start_ms / 1000)}
                  className="font-mono text-[11px] text-zinc-400 hover:text-purple-400 transition-colors flex items-center gap-1"
                  title="Click to jump to segment start"
                >
                  <Clock className="w-3 h-3 opacity-60" />
                  {formatDuration(segment.start_ms / 1000)}
                </button>
              </div>

              {/* Segment Words with Word-Level Click to Seek & Live Active Word Highlight */}
              <p className="text-xs sm:text-sm leading-relaxed text-zinc-200">
                {segment.words && segment.words.length > 0 ? (
                  segment.words.map((w: TranscriptWord) => {
                    const isWordActive = activeWordId === w.id;
                    const isSearchMatched =
                      searchQuery.trim() !== "" &&
                      w.word.toLowerCase().includes(searchQuery.toLowerCase());

                    return (
                      <span
                        key={w.id}
                        id={`word-${w.id}`}
                        ref={isWordActive ? activeWordRef : null}
                        onClick={() => onSeek(w.start_ms / 1000)}
                        className={`cursor-pointer px-0.5 py-0.5 rounded transition-all inline-block ${
                          isWordActive
                            ? "bg-purple-500 text-white font-semibold shadow-md shadow-purple-500/40 scale-105"
                            : isSearchMatched
                            ? "bg-amber-400/30 text-amber-200 font-medium underline"
                            : "hover:bg-white/10 hover:text-white"
                        }`}
                        title={`${formatDuration(w.start_ms / 1000)} - ${w.word}`}
                      >
                        {w.word}{" "}
                      </span>
                    );
                  })
                ) : (
                  <span
                    onClick={() => onSeek(segment.start_ms / 1000)}
                    className="cursor-pointer hover:text-white"
                  >
                    {segment.text}
                  </span>
                )}
              </p>
            </div>
          );
        })}
      </div>

      {/* Floating "Jump to current playback" button when auto-scroll is paused */}
      {userHasScrolled && !autoScroll && (
        <button
          onClick={handleResumeAutoScroll}
          className="absolute bottom-4 right-4 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-purple-600 text-white shadow-xl hover:bg-purple-500 active:scale-95 transition-all animate-bounce"
        >
          <ArrowDown className="w-3.5 h-3.5" />
          <span>Jump to current</span>
        </button>
      )}
    </div>
  );
}
