"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  CaptionStyle,
  ExportPreset,
  UserPlanMe,
  ClipCaptions,
  ClipCleanup,
  ClipCleanupAnalyzeResult,
  ExportRecord,
} from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import {
  Sparkles,
  Scissors,
  CheckCircle2,
  AlertTriangle,
  Download,
  Loader2,
  Play,
  Pause,
  Layers,
  Crown,
  Share2,
  Zap,
  Info,
  Type,
  Maximize2,
  Film,
} from "lucide-react";

interface ExportPanelProps {
  clipId: string;
  clipStartMs: number;
  clipEndMs: number;
  videoProxyUrl?: string | null;
  videoDurationMs?: number;
  onClose?: () => void;
}

export function ExportPanel({
  clipId,
  clipStartMs,
  clipEndMs,
  videoProxyUrl,
  videoDurationMs,
  onClose,
}: ExportPanelProps) {
  // Styles, presets, plan state
  const [styles, setStyles] = useState<CaptionStyle[]>([]);
  const [presets, setPresets] = useState<ExportPreset[]>([]);
  const [userPlan, setUserPlan] = useState<UserPlanMe | null>(null);

  // Selected config
  const [selectedStyleKey, setSelectedStyleKey] = useState<string>("bold_pop");
  const [selectedPresetKey, setSelectedPresetKey] = useState<string>("tiktok");
  const [captionsEnabled, setCaptionsEnabled] = useState<boolean>(true);
  const [cleanupEnabled, setCleanupEnabled] = useState<boolean>(true);

  // Loaded data
  const [captions, setCaptions] = useState<ClipCaptions | null>(null);
  const [cleanupAnalysis, setCleanupAnalysis] = useState<ClipCleanupAnalyzeResult | null>(null);
  const [exportsList, setExportsList] = useState<ExportRecord[]>([]);

  // Export job in-flight & progress
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const [exportProgress, setExportProgress] = useState<number>(0);
  const [activeExportRecord, setActiveExportRecord] = useState<ExportRecord | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Preview video playback
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentPlaybackMs, setCurrentPlaybackMs] = useState<number>(clipStartMs);

  const [loading, setLoading] = useState<boolean>(true);

  // Initial load
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [stylesData, presetsData, planData, capsData, exportsData] = await Promise.all([
          api.getCaptionStyles().catch(() => []),
          api.getExportPresets().catch(() => []),
          api.getMyPlan().catch(() => null),
          api.getClipCaptions(clipId).catch(() => null),
          api.listClipExports(clipId).catch(() => []),
        ]);

        setStyles(stylesData);
        setPresets(presetsData);
        setUserPlan(planData);
        if (capsData) {
          setCaptions(capsData);
          if (capsData.style_key) setSelectedStyleKey(capsData.style_key);
        }
        setExportsList(exportsData);

        // Fetch cleanup analysis
        const analysis = await api.analyzeClipCleanup(clipId, { remove_fillers: true, remove_silence: true }).catch(() => null);
        if (analysis) setCleanupAnalysis(analysis);
      } catch (err) {
        console.error("Failed to load export options:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [clipId]);

  // Handle cleanup toggle
  const handleToggleCleanup = async (enabled: boolean) => {
    setCleanupEnabled(enabled);
    try {
      const res = await api.analyzeClipCleanup(clipId, {
        remove_fillers: enabled,
        remove_silence: enabled,
      });
      setCleanupAnalysis(res);
    } catch (e) {
      console.error("Cleanup analysis error:", e);
    }
  };

  // Selected preset and style objects
  const currentPreset = useMemo(() => {
    return presets.find((p) => p.key === selectedPresetKey) || presets[0];
  }, [presets, selectedPresetKey]);

  const currentStyle = useMemo(() => {
    return styles.find((s) => s.key === selectedStyleKey) || styles[0];
  }, [styles, selectedStyleKey]);

  // Duration calculations
  const rawClipDurationS = (clipEndMs - clipStartMs) / 1000.0;
  const cleanDurationS = cleanupEnabled && cleanupAnalysis ? cleanupAnalysis.clean_duration_ms / 1000.0 : rawClipDurationS;
  const savedDurationS = cleanupEnabled && cleanupAnalysis ? cleanupAnalysis.saved_seconds : 0;
  const cutsCount = cleanupEnabled && cleanupAnalysis ? cleanupAnalysis.cut_count : 0;

  // Recommended duration warning
  const durationWarning = useMemo(() => {
    if (!currentPreset) return null;
    if (cleanDurationS > currentPreset.max_duration_s) {
      return `Clip duration (${cleanDurationS.toFixed(1)}s) exceeds ${currentPreset.name} recommendation (${currentPreset.max_duration_s}s).`;
    }
    return null;
  }, [currentPreset, cleanDurationS]);

  // Current active words for live preview
  const activeCaptionLine = useMemo(() => {
    if (!captionsEnabled || !captions || !captions.words) return null;
    const words = captions.words.filter((w) => !w.deleted);
    // Find active word or nearest word around currentPlaybackMs
    const activeWordIdx = words.findIndex((w) => currentPlaybackMs >= w.start_ms && currentPlaybackMs <= w.end_ms);
    if (activeWordIdx === -1) {
      // Find closest word within 500ms
      const nearby = words.find((w) => Math.abs(w.start_ms - currentPlaybackMs) <= 600);
      if (!nearby) return null;
      return { words: [nearby], activeIdx: 0 };
    }
    // Take a small window of 3 words around active word
    const startIdx = Math.max(0, activeWordIdx - 1);
    const endIdx = Math.min(words.length, startIdx + 3);
    return {
      words: words.slice(startIdx, endIdx),
      activeIdx: activeWordIdx - startIdx,
    };
  }, [captionsEnabled, captions, currentPlaybackMs]);

  // Handle Video time update
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const curMs = videoRef.current.currentTime * 1000;
      if (curMs > clipEndMs) {
        videoRef.current.currentTime = clipStartMs / 1000.0;
        setCurrentPlaybackMs(clipStartMs);
      } else {
        setCurrentPlaybackMs(curMs);
      }
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        if (videoRef.current.currentTime < clipStartMs / 1000.0 || videoRef.current.currentTime >= clipEndMs / 1000.0) {
          videoRef.current.currentTime = clipStartMs / 1000.0;
        }
        videoRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  // Launch Export
  const handleExport = async (batch: boolean = false) => {
    setExportError(null);
    setIsExporting(true);
    setExportProgress(10);

    try {
      // Update captions style if changed
      if (captions && selectedStyleKey) {
        await api.updateClipCaptions(clipId, {
          words: captions.words,
          style_key: selectedStyleKey,
        }).catch(() => null);
      }

      const payload = batch
        ? { presets: ["tiktok", "reels", "shorts", "generic_vertical"], style_key: selectedStyleKey, force: true }
        : { preset_key: selectedPresetKey, style_key: selectedStyleKey, force: true };

      const newExports = await api.createClipExports(clipId, payload);
      if (newExports && newExports.length > 0) {
        const primary = newExports[0];
        setActiveExportId(primary.id);
        setActiveExportRecord(primary);
        setExportsList((prev) => [primary, ...prev.filter((e) => e.id !== primary.id)]);

        // Setup SSE listener for export progress
        const eventSource = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/exports/${primary.id}/events`);
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.progress !== undefined) {
              setExportProgress(data.progress);
            }
            if (data.type === "export_ready" || data.status === "succeeded") {
              setIsExporting(false);
              setExportProgress(100);
              eventSource.close();
              // Refresh export record for download url
              api.getExport(primary.id).then((fresh) => {
                setActiveExportRecord(fresh);
                setExportsList((prev) => [fresh, ...prev.filter((e) => e.id !== fresh.id)]);
              });
            } else if (data.type === "export_failed" || data.status === "failed") {
              setIsExporting(false);
              setExportError(data.error || "Export failed.");
              eventSource.close();
            }
          } catch (e) {
            console.error("SSE parse error", e);
          }
        };

        eventSource.onerror = () => {
          eventSource.close();
          // Fallback poll
          setTimeout(async () => {
            const poll = await api.getExport(primary.id).catch(() => null);
            if (poll) {
              setActiveExportRecord(poll);
              if (poll.status === "succeeded") {
                setIsExporting(false);
                setExportProgress(100);
              }
            }
          }, 3000);
        };
      }
    } catch (err: any) {
      setIsExporting(false);
      setExportError(err?.message || "Failed to trigger export");
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-3" />
        <p className="text-sm">Preparing studio render engine & presets...</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="px-6 py-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl text-white shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              Export & Subtitle Studio
              <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                1080x1920 60fps
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Single-pass vertical crop, word-level ASS captions, filler cleanup, and loudnorm audio.
            </p>
          </div>
        </div>

        {/* Plan / Quota Badge */}
        {userPlan && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-700/60 rounded-xl text-xs">
            <Crown className={`w-3.5 h-3.5 ${userPlan.plan.key === 'free' ? 'text-amber-400' : 'text-emerald-400'}`} />
            <span className="font-semibold text-slate-200 capitalize">{userPlan.plan.name}</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-300">
              {userPlan.monthly_exports_used} / {userPlan.monthly_exports_limit} exports
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6">
        {/* Left Column: Live 9:16 Interactive Canvas Preview */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="relative w-[280px] h-[498px] bg-black rounded-2xl overflow-hidden shadow-2xl border-2 border-slate-700/80 flex items-center justify-center group">
            {videoProxyUrl ? (
              <video
                ref={videoRef}
                src={videoProxyUrl}
                className="w-full h-full object-cover"
                onTimeUpdate={handleTimeUpdate}
                playsInline
                muted
              />
            ) : (
              <div className="text-center p-4 text-slate-500 text-xs">
                <Film className="w-8 h-8 mx-auto mb-2 opacity-50" />
                No preview stream
              </div>
            )}

            {/* Live Subtitle Overlay matching ASS spec */}
            {captionsEnabled && activeCaptionLine && (
              <div className="absolute inset-x-0 bottom-16 px-4 flex flex-col items-center justify-center pointer-events-none z-20">
                <div
                  className={`text-center transition-all duration-150 ${
                    selectedStyleKey === "bold_pop"
                      ? "font-black tracking-wide uppercase text-white"
                      : selectedStyleKey === "clean_minimal"
                      ? "font-semibold text-white tracking-normal"
                      : "font-bold text-slate-200 uppercase"
                  }`}
                  style={{
                    fontSize: selectedStyleKey === "bold_pop" ? "20px" : selectedStyleKey === "clean_minimal" ? "16px" : "18px",
                    textShadow:
                      selectedStyleKey === "bold_pop"
                        ? "0 0 4px #000, 2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000"
                        : "0 2px 4px rgba(0,0,0,0.8)",
                  }}
                >
                  {activeCaptionLine.words.map((w, idx) => {
                    const isActive = idx === activeCaptionLine.activeIdx;
                    return (
                      <span
                        key={idx}
                        className={`inline-block mx-1 transition-transform duration-100 ${
                          isActive && selectedStyleKey === "bold_pop"
                            ? "scale-110 text-yellow-300 font-extrabold"
                            : isActive && selectedStyleKey === "karaoke"
                            ? "text-amber-400 scale-105"
                            : w.emphasis
                            ? "text-sky-300 font-bold"
                            : "text-white"
                        }`}
                      >
                        {w.text}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Free Tier Watermark Overlay Badge */}
            {userPlan?.watermark_required && (
              <div className="absolute top-4 right-4 px-2 py-0.5 bg-black/60 backdrop-blur-md rounded border border-white/20 text-[10px] font-mono font-semibold text-white/80 pointer-events-none">
                Clip It Up
              </div>
            )}

            {/* Play/Pause Overlay button */}
            <button
              onClick={togglePlay}
              className="absolute inset-0 m-auto w-12 h-12 rounded-full bg-slate-900/80 backdrop-blur-md border border-white/20 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110"
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </button>
          </div>

          <p className="text-[11px] text-slate-500 mt-2 text-center">
            Interactive canvas preview driven by unified ASS spec
          </p>
        </div>

        {/* Right Column: Settings & Export Controls */}
        <div className="lg:col-span-7 flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            {/* 1. Subtitle Style Packs */}
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Type className="w-3.5 h-3.5 text-indigo-400" />
                  Subtitle Style Pack
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400">Captions</span>
                  <button
                    onClick={() => setCaptionsEnabled(!captionsEnabled)}
                    className={`w-9 h-5 rounded-full transition-colors relative ${
                      captionsEnabled ? "bg-indigo-600" : "bg-slate-700"
                    }`}
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white transition-transform absolute top-0.75 left-0.75 ${
                        captionsEnabled ? "translate-x-4" : ""
                      }`}
                    />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                {styles.map((style) => {
                  const isSelected = selectedStyleKey === style.key;
                  return (
                    <button
                      key={style.key}
                      onClick={() => setSelectedStyleKey(style.key)}
                      className={`p-3 rounded-xl border text-left transition-all relative ${
                        isSelected
                          ? "bg-indigo-950/60 border-indigo-500 shadow-lg shadow-indigo-500/10 text-white ring-1 ring-indigo-500"
                          : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <div className="text-xs font-bold mb-1">{style.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {style.key === "bold_pop" && "Pop scale + Yellow"}
                        {style.key === "clean_minimal" && "Minimal + Cyan"}
                        {style.key === "karaoke" && "Sweeping \\k tags"}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 2. Platform Preset Selector */}
            <div>
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                Platform Export Preset
              </label>

              <div className="grid grid-cols-2 gap-2.5">
                {presets.map((preset) => {
                  const isSelected = selectedPresetKey === preset.key;
                  return (
                    <button
                      key={preset.key}
                      onClick={() => setSelectedPresetKey(preset.key)}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        isSelected
                          ? "bg-purple-950/50 border-purple-500 text-white ring-1 ring-purple-500"
                          : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold">{preset.name}</span>
                        <span className="text-[10px] font-mono text-purple-300 bg-purple-950/80 px-1.5 py-0.5 rounded">
                          {preset.max_duration_s}s cap
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 line-clamp-1">{preset.notes}</div>
                    </button>
                  );
                })}
              </div>

              {/* Length recommendation warning */}
              {durationWarning && (
                <div className="mt-2.5 p-2.5 bg-amber-950/40 border border-amber-800/50 rounded-xl flex items-center gap-2 text-xs text-amber-300">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-400" />
                  <span>{durationWarning}</span>
                </div>
              )}
            </div>

            {/* 3. AI Filler & Silence Removal Toggle */}
            <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-950/80 border border-emerald-800/60 rounded-lg text-emerald-400">
                  <Scissors className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    Remove Fillers & Silences
                    {cutsCount > 0 && (
                      <span className="text-[10px] px-2 py-0.5 bg-emerald-950 border border-emerald-700 text-emerald-300 rounded-full font-mono">
                        Saved {savedDurationS.toFixed(1)}s ({cutsCount} cuts)
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Smart gap shortening, low-energy zero-crossing cut snapping & 40ms crossfade.
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleToggleCleanup(!cleanupEnabled)}
                className={`w-10 h-6 rounded-full transition-colors relative ${
                  cleanupEnabled ? "bg-emerald-600" : "bg-slate-700"
                }`}
              >
                <div
                  className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-1 left-1 ${
                    cleanupEnabled ? "translate-x-4" : ""
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Export Action Area */}
          <div className="space-y-3 pt-3 border-t border-slate-800">
            {/* Free Tier Upgrade CTA note */}
            {userPlan?.watermark_required && (
              <div className="p-2.5 bg-indigo-950/30 border border-indigo-900/50 rounded-xl flex items-center justify-between text-xs text-indigo-300">
                <div className="flex items-center gap-2">
                  <Info className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                  <span>Free tier includes subtle corner watermark.</span>
                </div>
                <button className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg text-[11px] transition-colors">
                  Upgrade
                </button>
              </div>
            )}

            {/* Error banner */}
            {exportError && (
              <div className="p-3 bg-red-950/60 border border-red-800 rounded-xl text-xs text-red-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 text-red-400" />
                <span>{exportError}</span>
              </div>
            )}

            {/* In-Flight Progress */}
            {isExporting && (
              <div className="space-y-1.5 p-3 bg-slate-950 border border-indigo-900/60 rounded-xl">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-indigo-300 flex items-center gap-2 font-medium">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Rendering FFmpeg Single-Pass Graph...
                  </span>
                  <span className="text-white font-mono font-bold">{Math.round(exportProgress)}%</span>
                </div>
                <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 transition-all duration-300"
                    style={{ width: `${exportProgress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Download Button if active export ready */}
            {activeExportRecord && activeExportRecord.status === "succeeded" && activeExportRecord.download_url && (
              <a
                href={activeExportRecord.download_url}
                target="_blank"
                rel="noreferrer"
                className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition-all hover:scale-[1.01]"
              >
                <Download className="w-4 h-4" />
                Download Ready MP4 ({formatDuration((activeExportRecord.duration_ms || 0) / 1000.0)})
              </a>
            )}

            {/* Export Trigger Buttons */}
            <div className="flex gap-2.5">
              <button
                disabled={isExporting}
                onClick={() => handleExport(false)}
                className="flex-1 py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:pointer-events-none"
              >
                <Zap className="w-4 h-4 text-amber-300" />
                Export {currentPreset.name.split(" ")[0]} (1080x1920)
              </button>

              <button
                disabled={isExporting}
                onClick={() => handleExport(true)}
                title="Export all platform presets in one batch"
                className="px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl border border-slate-700 transition-colors disabled:opacity-50"
              >
                All Presets
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
