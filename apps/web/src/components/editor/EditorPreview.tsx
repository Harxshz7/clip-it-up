"use client";

import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useEditorStore } from "@/lib/editorStore";
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Gauge,
  Layers,
  Shield,
  Info,
  Sparkles,
  Maximize2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface EditorPreviewProps {
  proxyUrl?: string | null;
  videoTitle?: string;
  onCheckpoint?: () => void;
}

export const EditorPreview: React.FC<EditorPreviewProps> = ({
  proxyUrl,
  videoTitle,
  onCheckpoint,
}) => {
  const {
    doc,
    edl,
    currentTimeMs,
    isPlaying,
    playbackRate,
    loopRange,
    showSafeZone,
    setCurrentTimeMs,
    setIsPlaying,
    setPlaybackRate,
    setLoopRange,
    setShowSafeZone,
    setRange,
    undo,
    redo,
    canUndo,
    canRedo,
    save,
  } = useEditorStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [safeZonePlatform, setSafeZonePlatform] = useState<"tiktok" | "reels" | "shorts">("tiktok");
  const [showParityNotes, setShowParityNotes] = useState(false);
  const skipGraceRef = useRef(false);

  const startMs = doc?.range.start_ms || 0;
  const endMs = doc?.range.end_ms || 10000;
  const durationMs = Math.max(1, endMs - startMs);

  // Synchronize playback rate
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  // Synchronize play / pause state
  useEffect(() => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.play().catch(() => setIsPlaying(false));
    } else {
      videoRef.current.pause();
    }
  }, [isPlaying, setIsPlaying]);

  // Calculate active crop from keyframes
  const activeCrop = useMemo(() => {
    const defaultCrop = { cx: 0.5, cy: 0.5, w: 0.5625, h: 1.0 }; // 9:16 inside 16:9 is 9/16 = 0.5625
    if (!doc || !doc.reframe.keyframes || doc.reframe.keyframes.length === 0) {
      return defaultCrop;
    }

    const kfs = doc.reframe.keyframes;
    if (kfs.length === 1) {
      return {
        cx: kfs[0].x,
        cy: kfs[0].y,
        w: kfs[0].width || defaultCrop.w,
        h: kfs[0].height || defaultCrop.h,
      };
    }

    // Relative offset within clip or absolute
    const firstT = kfs[0].t_ms;
    const isRelative = firstT < startMs;
    const relTime = isRelative ? currentTimeMs - startMs : currentTimeMs;

    let prev = kfs[0];
    let next = kfs[kfs.length - 1];

    for (let i = 0; i < kfs.length; i++) {
      if (kfs[i].t_ms <= relTime) {
        prev = kfs[i];
      }
      if (kfs[i].t_ms >= relTime) {
        next = kfs[i];
        break;
      }
    }

    if (prev === next || prev.t_ms === next.t_ms) {
      return {
        cx: prev.x,
        cy: prev.y,
        w: prev.width || defaultCrop.w,
        h: prev.height || defaultCrop.h,
      };
    }

    const span = next.t_ms - prev.t_ms;
    const factor = Math.max(0, Math.min(1, (relTime - prev.t_ms) / span));

    return {
      cx: prev.x + (next.x - prev.x) * factor,
      cy: prev.y + (next.y - prev.y) * factor,
      w: (prev.width || defaultCrop.w) + ((next.width || defaultCrop.w) - (prev.width || defaultCrop.w)) * factor,
      h: (prev.height || defaultCrop.h) + ((next.height || defaultCrop.h) - (prev.height || defaultCrop.h)) * factor,
    };
  }, [doc, currentTimeMs, startMs]);

  // Handle video timeupdate and skip removed cuts
  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current || !doc) return;
    const currMs = Math.round(videoRef.current.currentTime * 1000);

    // Check if within bounds
    if (currMs >= doc.range.end_ms) {
      if (loopRange) {
        videoRef.current.currentTime = doc.range.start_ms / 1000.0;
        setCurrentTimeMs(doc.range.start_ms);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
        setCurrentTimeMs(doc.range.end_ms);
      }
      return;
    }

    // Skip removals using EDL
    if (edl && edl.removals && !skipGraceRef.current) {
      for (const r of edl.removals) {
        if (currMs >= r.start_ms && currMs < r.end_ms) {
          // Seamless jump with audio micro-fade to avoid click
          skipGraceRef.current = true;
          const origVol = videoRef.current.volume;
          videoRef.current.volume = 0.05;
          videoRef.current.currentTime = (r.end_ms + 10) / 1000.0;
          setTimeout(() => {
            if (videoRef.current) videoRef.current.volume = origVol;
            skipGraceRef.current = false;
          }, 40);
          setCurrentTimeMs(r.end_ms);
          return;
        }
      }
    }

    setCurrentTimeMs(currMs);
  }, [doc, edl, loopRange, setCurrentTimeMs, setIsPlaying]);

  // Active caption text for current time
  const activeCaption = useMemo(() => {
    if (!doc || !doc.captions || !doc.captions.enabled || !doc.captions.words) {
      return null;
    }

    const words = doc.captions.words.filter((w) => !w.deleted);
    // Find current word
    const currentWord = words.find(
      (w) => w.start_ms <= currentTimeMs && currentTimeMs <= w.end_ms
    );

    if (!currentWord) {
      // Find nearby window of 3 words
      const nearestIdx = words.findIndex((w) => w.start_ms > currentTimeMs);
      const targetIdx = nearestIdx > 0 ? nearestIdx - 1 : 0;
      const nearby = words.slice(Math.max(0, targetIdx - 1), targetIdx + 2);
      if (nearby.length > 0 && Math.abs(nearby[0].start_ms - currentTimeMs) < 600) {
        return nearby;
      }
      return null;
    }

    // Chunk of up to 4 words around active word
    const idx = words.indexOf(currentWord);
    const startIdx = Math.max(0, idx - 1);
    const endIdx = Math.min(words.length, idx + 3);
    return words.slice(startIdx, endIdx);
  }, [doc, currentTimeMs]);

  // Keyboard navigation & transport shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input or textarea
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      // Cmd/Ctrl + Z / Shift + Z
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) {
          if (canRedo()) redo();
        } else {
          if (canUndo()) undo();
        }
        return;
      }

      // Cmd/Ctrl + S
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        save(true, "manual_checkpoint");
        if (onCheckpoint) onCheckpoint();
        return;
      }

      // Space: toggle play/pause
      if (e.code === "Space") {
        e.preventDefault();
        setIsPlaying(!isPlaying);
        return;
      }

      // J / K / L
      if (e.key === "k" || e.key === "K") {
        setIsPlaying(false);
      } else if (e.key === "j" || e.key === "J") {
        // Step back 1s
        if (videoRef.current) {
          const t = Math.max(startMs / 1000.0, videoRef.current.currentTime - 1.0);
          videoRef.current.currentTime = t;
          setCurrentTimeMs(Math.round(t * 1000));
        }
      } else if (e.key === "l" || e.key === "L") {
        // Step forward 1s or toggle play
        if (!isPlaying) {
          setIsPlaying(true);
        } else {
          setPlaybackRate(playbackRate === 1.0 ? 1.5 : playbackRate === 1.5 ? 2.0 : 1.0);
        }
      }

      // Arrow keys: Left / Right
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        const delta = e.shiftKey ? 1000 : 33; // 1s with shift, 1 frame without
        if (videoRef.current) {
          const newTime = Math.max(startMs, currentTimeMs - delta);
          videoRef.current.currentTime = newTime / 1000.0;
          setCurrentTimeMs(newTime);
        }
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        const delta = e.shiftKey ? 1000 : 33;
        if (videoRef.current) {
          const newTime = Math.min(endMs, currentTimeMs + delta);
          videoRef.current.currentTime = newTime / 1000.0;
          setCurrentTimeMs(newTime);
        }
      }

      // [ / ] trim in / out
      if (e.key === "[") {
        e.preventDefault();
        if (doc && currentTimeMs < doc.range.end_ms - 2000) {
          setRange({ start_ms: currentTimeMs, end_ms: doc.range.end_ms });
        }
      } else if (e.key === "]") {
        e.preventDefault();
        if (doc && currentTimeMs > doc.range.start_ms + 2000) {
          setRange({ start_ms: doc.range.start_ms, end_ms: currentTimeMs });
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isPlaying,
    currentTimeMs,
    playbackRate,
    doc,
    startMs,
    endMs,
    canUndo,
    canRedo,
    undo,
    redo,
    save,
    setIsPlaying,
    setPlaybackRate,
    setCurrentTimeMs,
    setRange,
    onCheckpoint,
  ]);

  const seekTo = (ms: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = ms / 1000.0;
      setCurrentTimeMs(ms);
    }
  };

  const progressPercent = Math.max(
    0,
    Math.min(100, ((currentTimeMs - startMs) / durationMs) * 100)
  );

  return (
    <div className="flex flex-col h-full bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Top Header bar with status indicators */}
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white tracking-wide flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            9:16 Preview (720p Proxy)
          </span>
          <span className="text-[11px] font-mono text-zinc-400 bg-zinc-800/80 px-1.5 py-0.5 rounded">
            {((currentTimeMs - startMs) / 1000.0).toFixed(1)}s / {(durationMs / 1000.0).toFixed(1)}s
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowParityNotes(!showParityNotes)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 transition-colors"
            title="Preview matches export details"
          >
            <Info className="w-3 h-3 text-purple-400" />
            <span>Parity Notes</span>
          </button>

          <button
            onClick={() => setShowSafeZone(!showSafeZone)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
              showSafeZone
                ? "bg-purple-600/40 text-purple-200 border border-purple-500/50"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            }`}
          >
            <Shield className="w-3 h-3" />
            <span>Safe Zones</span>
          </button>
        </div>
      </div>

      {/* Parity Notes Dropdown */}
      {showParityNotes && (
        <div className="bg-purple-950/40 border-b border-purple-800/40 px-4 py-2 text-[11px] text-purple-200 space-y-1">
          <div className="font-semibold flex items-center gap-1.5 text-purple-100">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            Preview matches export via single versioned edit doc. Known preview differences:
          </div>
          <ul className="list-disc pl-4 space-y-0.5 text-purple-300/90">
            <li>Proxy preview uses 720p H.264; export renders from original 1080p source video.</li>
            <li>Real-time crop path is CSS/Canvas GPU-simulated; export uses hardware-accelerated FFmpeg crop.</li>
            <li>Browser sub-pixel fonts differ subtly from libass ASS subtitles engine.</li>
          </ul>
        </div>
      )}

      {/* Center 9:16 Preview Canvas */}
      <div
        ref={containerRef}
        className="flex-1 relative flex items-center justify-center p-4 bg-black/90 overflow-hidden select-none min-h-[420px]"
      >
        {/* 9:16 Aspect Phone Container */}
        <div
          className="relative rounded-2xl overflow-hidden border-2 border-zinc-700 shadow-2xl bg-black"
          style={{ width: "260px", height: "462px" }} // Standard 9:16 container
        >
          {/* Proxy Video with Real-Time Crop Path Transformation */}
          {proxyUrl ? (
            <div className="w-full h-full relative overflow-hidden bg-black">
              <div
                className="absolute pointer-events-none transition-transform duration-75 origin-top-left"
                style={{
                  width: `${(1.0 / activeCrop.w) * 100}%`,
                  height: "100%",
                  left: `${-((activeCrop.cx - activeCrop.w / 2) / activeCrop.w) * 100}%`,
                  top: `${-((activeCrop.cy - activeCrop.h / 2) / activeCrop.h) * 100}%`,
                }}
              >
                <video
                  ref={videoRef}
                  src={proxyUrl}
                  className="w-full h-full object-cover"
                  onTimeUpdate={handleTimeUpdate}
                  muted={isMuted}
                  playsInline
                  preload="metadata"
                />
              </div>

              {/* Dynamic Styled Captions Overlay */}
              {doc?.captions.enabled && activeCaption && (
                <div
                  className="absolute inset-x-3 bottom-14 flex flex-col items-center justify-center text-center pointer-events-none z-20"
                  style={{
                    fontFamily: doc.captions.style_overrides?.font_family || "Outfit, sans-serif",
                    textTransform: doc.captions.style_overrides?.uppercase !== false ? "uppercase" : "none",
                  }}
                >
                  <div className="bg-black/40 backdrop-blur-xs px-2.5 py-1 rounded-lg">
                    {activeCaption.map((w, i) => {
                      const isWordActive =
                        w.start_ms <= currentTimeMs && currentTimeMs <= w.end_ms;
                      return (
                        <span
                          key={i}
                          className={`inline-block mx-0.5 font-black text-sm tracking-wide transition-all ${
                            isWordActive
                              ? "text-yellow-300 scale-110 drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]"
                              : w.emphasis
                              ? "text-emerald-400 font-bold drop-shadow"
                              : "text-white drop-shadow"
                          }`}
                        >
                          {w.text}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Safe Zone Overlay */}
              {showSafeZone && (
                <div className="absolute inset-0 pointer-events-none z-30 border-2 border-dashed border-red-500/40">
                  {/* Top zone (profile / sound) */}
                  <div className="absolute top-0 inset-x-0 h-10 bg-red-500/10 border-b border-red-500/30 flex items-center justify-center">
                    <span className="text-[9px] font-mono text-red-300/80">Header Safe Zone</span>
                  </div>
                  {/* Right side icons zone */}
                  <div className="absolute top-10 bottom-20 right-0 w-11 bg-red-500/10 border-l border-red-500/30 flex items-center justify-center">
                    <span className="text-[8px] font-mono text-red-300/80 -rotate-90">Actions</span>
                  </div>
                  {/* Bottom captions & CTA zone */}
                  <div className="absolute bottom-0 inset-x-0 h-16 bg-red-500/10 border-t border-red-500/30 flex items-center justify-center">
                    <span className="text-[9px] font-mono text-red-300/80">Caption & Audio Zone</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-zinc-500 text-xs p-4 text-center">
              <div className="w-8 h-8 rounded-full border-2 border-purple-500 border-t-transparent animate-spin mb-2" />
              <span>Loading Proxy Stream...</span>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Transport Controls */}
      <div className="px-3 py-2 bg-zinc-900 border-t border-zinc-800 space-y-2">
        {/* Scrubbing timeline bar */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-zinc-400 w-10 text-right">
            {((currentTimeMs - startMs) / 1000.0).toFixed(1)}s
          </span>
          <div
            className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden cursor-pointer relative"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
              seekTo(Math.round(startMs + pos * durationMs));
            }}
          >
            <div
              className="h-full bg-purple-500 transition-all duration-75 relative rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-zinc-400 w-10">
            {(durationMs / 1000.0).toFixed(1)}s
          </span>
        </div>

        {/* Buttons Bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Play / Pause */}
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="p-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white transition-colors"
              title="Play / Pause (Space)"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
            </button>

            {/* Loop range toggle */}
            <button
              onClick={() => setLoopRange(!loopRange)}
              className={`p-1.5 rounded-lg transition-colors ${
                loopRange ? "bg-purple-950 text-purple-300 border border-purple-700" : "text-zinc-400 hover:text-white"
              }`}
              title="Loop clip range"
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            {/* Step -1s / +1s */}
            <button
              onClick={() => seekTo(Math.max(startMs, currentTimeMs - 1000))}
              className="p-1 text-zinc-400 hover:text-white transition-colors"
              title="Back 1s (J)"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => seekTo(Math.min(endMs, currentTimeMs + 1000))}
              className="p-1 text-zinc-400 hover:text-white transition-colors"
              title="Forward 1s (L)"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            {/* Volume mute */}
            <button
              onClick={() => setIsMuted(!isMuted)}
              className="p-1 text-zinc-400 hover:text-white transition-colors"
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
            </button>
          </div>

          {/* Speed & Set Trim [ ] shortcuts */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const nextRate = playbackRate === 1.0 ? 1.5 : playbackRate === 1.5 ? 2.0 : playbackRate === 2.0 ? 0.5 : 1.0;
                setPlaybackRate(nextRate);
              }}
              className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 hover:text-white transition-colors"
              title="Playback speed"
            >
              {playbackRate}x
            </button>

            <button
              onClick={() => setRange({ start_ms: currentTimeMs, end_ms: doc?.range.end_ms || endMs })}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              title="Set In Point ([)"
            >
              [ In
            </button>
            <button
              onClick={() => setRange({ start_ms: doc?.range.start_ms || startMs, end_ms: currentTimeMs })}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              title="Set Out Point (])"
            >
              Out ]
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
