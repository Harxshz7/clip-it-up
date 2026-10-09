'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Clip,
  ReframeResponse,
  ReframeKeyframe,
  ReframeMode,
} from '@clip-it-up/shared';
import { api } from '../lib/api';

interface ReframeViewerProps {
  clip: Clip;
  proxyUrl?: string | null;
  onClose?: () => void;
  token?: string | null;
}

export const ReframeViewer: React.FC<ReframeViewerProps> = ({
  clip,
  proxyUrl,
  onClose,
  token,
}) => {
  const [reframeData, setReframeData] = useState<ReframeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [currentTimeMs, setCurrentTimeMs] = useState(clip.start_ms);
  const [isPlaying, setIsPlaying] = useState(false);
  const [sideBySide, setSideBySide] = useState(true);
  const [showSafeZones, setShowSafeZones] = useState(true);
  const [safeZonePlatform, setSafeZonePlatform] = useState<'tiktok' | 'reels' | 'shorts'>('tiktok');

  // Keyframes and editing
  const [keyframes, setKeyframes] = useState<ReframeKeyframe[]>([]);
  const [selectedKeyframeIndex, setSelectedKeyframeIndex] = useState<number>(0);
  const [currentMode, setCurrentMode] = useState<ReframeMode>('speaker_track');

  // Dragging state
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartPos, setDragStartPos] = useState<{ x: number; y: number } | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const previewVideoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Sync preview video time with main video
  useEffect(() => {
    if (previewVideoRef.current && Math.abs(previewVideoRef.current.currentTime - currentTimeMs / 1000.0) > 0.1) {
      previewVideoRef.current.currentTime = currentTimeMs / 1000.0;
    }
  }, [currentTimeMs]);

  // 1. Fetch Reframe Data
  const loadReframe = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getClipReframe(clip.id, 'v1', token);
      setReframeData(res);
      setCurrentMode(res.mode);
      const kfs = res.active_keyframes && res.active_keyframes.length > 0
        ? res.active_keyframes
        : res.crop_path.keyframes;
      setKeyframes(kfs);
    } catch (err: any) {
      setError(err?.message || 'Failed to load reframe data');
    } finally {
      setLoading(false);
    }
  }, [clip.id, token]);

  useEffect(() => {
    loadReframe();
  }, [loadReframe]);

  // Sync video time to clip start
  useEffect(() => {
    if (videoRef.current && proxyUrl) {
      videoRef.current.currentTime = clip.start_ms / 1000.0;
    }
  }, [proxyUrl, clip.start_ms]);

  // 2. Get active crop at currentTimeMs
  const getInterpolatedKeyframe = useCallback((t_ms: number): ReframeKeyframe => {
    if (!keyframes || keyframes.length === 0) {
      return { t_ms, cx: 0.5, cy: 0.5, w: 0.3164, h: 1.0 };
    }
    if (keyframes.length === 1) return keyframes[0];

    // Find bounding keyframes
    let prev = keyframes[0];
    let next = keyframes[keyframes.length - 1];

    for (let i = 0; i < keyframes.length; i++) {
      if (keyframes[i].t_ms <= t_ms) {
        prev = keyframes[i];
      }
      if (keyframes[i].t_ms >= t_ms) {
        next = keyframes[i];
        break;
      }
    }

    if (prev.t_ms === next.t_ms) return prev;

    const alpha = Math.max(0, Math.min(1, (t_ms - prev.t_ms) / (next.t_ms - prev.t_ms)));
    return {
      t_ms,
      cx: prev.cx + alpha * (next.cx - prev.cx),
      cy: prev.cy + alpha * (next.cy - prev.cy),
      w: prev.w + alpha * (next.w - prev.w),
      h: prev.h + alpha * (next.h - prev.h),
    };
  }, [keyframes]);

  const activeCrop = getInterpolatedKeyframe(currentTimeMs);

  // 3. Time update loop
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const tMs = Math.round(videoRef.current.currentTime * 1000);
    if (tMs >= clip.end_ms) {
      videoRef.current.currentTime = clip.start_ms / 1000.0;
      setCurrentTimeMs(clip.start_ms);
      return;
    }
    setCurrentTimeMs(tMs);
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play();
      setIsPlaying(true);
    }
  };

  // 4. Save Debounce
  const saveKeyframes = useCallback((newKeyframes: ReframeKeyframe[], mode?: ReframeMode) => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        setSaving(true);
        const res = await api.updateClipReframe(clip.id, { keyframes: newKeyframes, mode: mode || currentMode }, token);
        setReframeData(res);
      } catch (err: any) {
        console.error('Failed to save reframe edit', err);
      } finally {
        setSaving(false);
      }
    }, 600);
  }, [clip.id, currentMode, token]);

  // 5. Nudge / Drag Crop Box
  const handleMouseDownOnCrop = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    setDragStartPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStartPos) return;

    const dxPx = e.clientX - dragStartPos.x;
    const dyPx = e.clientY - dragStartPos.y;

    const rect = e.currentTarget.getBoundingClientRect();
    const dxNorm = dxPx / rect.width;
    const dyNorm = dyPx / rect.height;

    setDragStartPos({ x: e.clientX, y: e.clientY });

    // Update current keyframe or insert one
    setKeyframes((prev) => {
      const updated = [...prev];
      let matchIdx = updated.findIndex((k) => Math.abs(k.t_ms - currentTimeMs) < 300);

      const targetW = activeCrop.w;
      const targetH = activeCrop.h;
      const halfW = targetW / 2;
      const halfH = targetH / 2;

      const newCx = Math.max(halfW, Math.min(1.0 - halfW, activeCrop.cx + dxNorm));
      const newCy = Math.max(halfH, Math.min(1.0 - halfH, activeCrop.cy + dyNorm));

      if (matchIdx >= 0) {
        updated[matchIdx] = {
          ...updated[matchIdx],
          cx: Number(newCx.toFixed(4)),
          cy: Number(newCy.toFixed(4)),
        };
      } else {
        const newKf: ReframeKeyframe = {
          t_ms: currentTimeMs,
          cx: Number(newCx.toFixed(4)),
          cy: Number(newCy.toFixed(4)),
          w: targetW,
          h: targetH,
        };
        updated.push(newKf);
        updated.sort((a, b) => a.t_ms - b.t_ms);
      }

      saveKeyframes(updated);
      return updated;
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragStartPos(null);
  };

  // 6. Reset to Auto
  const handleResetToAuto = async () => {
    try {
      setSaving(true);
      const res = await api.revertClipReframeEdits(clip.id, token);
      setReframeData(res);
      setCurrentMode(res.mode);
      setKeyframes(res.crop_path.keyframes);
    } catch (err: any) {
      setError(err?.message || 'Failed to revert edits');
    } finally {
      setSaving(false);
    }
  };

  // 7. Regenerate with Mode Switch
  const handleModeChange = async (newMode: ReframeMode) => {
    setCurrentMode(newMode);
    try {
      setSaving(true);
      const res = await api.regenerateClipReframe(clip.id, { mode_override: newMode }, token);
      setReframeData(res);
      setKeyframes(res.crop_path.keyframes);
    } catch (err: any) {
      setError(err?.message || 'Failed to regenerate with new mode');
    } finally {
      setSaving(false);
    }
  };

  // 8. Add Keyframe at Current Time
  const handleAddKeyframe = () => {
    setKeyframes((prev) => {
      const exists = prev.some((k) => Math.abs(k.t_ms - currentTimeMs) < 100);
      if (exists) return prev;
      const next = [...prev, { ...activeCrop, t_ms: currentTimeMs }].sort((a, b) => a.t_ms - b.t_ms);
      saveKeyframes(next);
      return next;
    });
  };

  // 9. Delete Keyframe
  const handleDeleteKeyframe = (index: number) => {
    if (keyframes.length <= 1) return;
    setKeyframes((prev) => {
      const next = prev.filter((_, i) => i !== index);
      saveKeyframes(next);
      return next;
    });
  };

  // Mode badge styling
  const getModeBadge = (mode: ReframeMode) => {
    switch (mode) {
      case 'speaker_track':
        return { label: 'Speaker Track', color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' };
      case 'balanced':
        return { label: 'Balanced (2-Shot)', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' };
      case 'center':
        return { label: 'Center Crop', color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' };
      case 'fit_blur':
        return { label: 'Fit Blur (16:9)', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' };
      default:
        return { label: mode, color: 'bg-slate-500/20 text-slate-300 border-slate-500/30' };
    }
  };

  const badge = getModeBadge(currentMode);
  const confPct = Math.round((reframeData?.confidence || 0.9) * 100);

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-6xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[95vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">9:16 Reframe Studio</h2>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${badge.color}`}>
              {badge.label}
            </span>
            <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
              Confidence: {confPct}%
            </span>
            {saving && <span className="text-xs text-indigo-400 animate-pulse">Saving changes...</span>}
            {reframeData?.has_edits && (
              <span className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                Manual Nudges Active
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setSideBySide(!sideBySide)}
              className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
            >
              {sideBySide ? 'Single View' : 'Side-by-Side'}
            </button>
            <button
              onClick={() => setShowSafeZones(!showSafeZones)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition ${
                showSafeZones ? 'bg-indigo-600/30 text-indigo-300 border-indigo-500/50' : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              Safe Zones
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Warning chip if face cut risk */}
        {reframeData?.flags.face_cut_risk && (
          <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2 flex items-center justify-between text-xs text-amber-300">
            <span>⚠️ Face bounding box extends near crop edge. Consider Fit Blur mode.</span>
            <button
              onClick={() => handleModeChange('fit_blur')}
              className="bg-amber-500/20 hover:bg-amber-500/30 px-2.5 py-1 rounded font-medium transition"
            >
              Switch to Fit Blur
            </button>
          </div>
        )}

        {/* Video Canvas Area */}
        <div className="flex-1 bg-black/80 flex items-center justify-center p-6 overflow-hidden min-h-[420px]">
          {loading ? (
            <div className="text-slate-400 flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <span>Analyzing & framing video...</span>
            </div>
          ) : error ? (
            <div className="text-rose-400 text-sm">{error}</div>
          ) : (
            <div className="flex items-center justify-center gap-8 w-full h-full">
              {/* Left: 16:9 Landscape Source with Crop Outline */}
              {sideBySide && (
                <div className="flex flex-col items-center gap-2">
                  <span className="text-xs text-slate-400 font-mono">16:9 Source & Crop Box</span>
                  <div
                    className="relative bg-slate-950 rounded-lg overflow-hidden border border-slate-800 select-none"
                    style={{ width: '480px', height: '270px' }}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                  >
                    {proxyUrl && (
                      <video
                        ref={videoRef}
                        src={proxyUrl}
                        className="w-full h-full object-contain pointer-events-none"
                        onTimeUpdate={handleTimeUpdate}
                        muted
                        playsInline
                      />
                    )}

                    {/* Draggable Crop Rectangle Overlay */}
                    {currentMode !== 'fit_blur' ? (
                      <div
                        onMouseDown={handleMouseDownOnCrop}
                        className="absolute border-2 border-indigo-400 bg-indigo-500/20 cursor-move transition-all duration-75 shadow-lg rounded"
                        style={{
                          left: `${(activeCrop.cx - activeCrop.w / 2) * 100}%`,
                          top: `${(activeCrop.cy - activeCrop.h / 2) * 100}%`,
                          width: `${activeCrop.w * 100}%`,
                          height: `${activeCrop.h * 100}%`,
                        }}
                      >
                        <div className="absolute top-1 left-1 bg-indigo-600 text-white text-[9px] font-mono px-1 rounded">
                          9:16
                        </div>
                        {/* Eyeline guide */}
                        <div className="absolute top-[33%] left-0 right-0 border-t border-dashed border-indigo-300/40 pointer-events-none" />
                      </div>
                    ) : (
                      <div className="absolute inset-0 border-2 border-dashed border-cyan-400/50 bg-cyan-500/10 flex items-center justify-center">
                        <span className="text-xs text-cyan-300 font-mono">Fit Blur (Entire Frame)</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Right: 9:16 Vertical Cropped Preview */}
              <div className="flex flex-col items-center gap-2">
                <span className="text-xs text-slate-400 font-mono">9:16 Mobile Output Preview</span>
                <div
                  className="relative bg-slate-950 rounded-2xl overflow-hidden border-2 border-slate-700 shadow-2xl"
                  style={{ width: '240px', height: '426px' }}
                >
                  {/* CSS transform crop simulation on proxy video */}
                  {currentMode === 'fit_blur' ? (
                    <div className="w-full h-full relative overflow-hidden bg-slate-950">
                      {/* Blurred background copy */}
                      {proxyUrl && (
                        <video
                          src={proxyUrl}
                          className="absolute inset-0 w-full h-full object-cover blur-md opacity-60 scale-125 pointer-events-none"
                          muted
                        />
                      )}
                      {/* Crisp centered 16:9 foreground */}
                      {proxyUrl && (
                        <video
                          ref={previewVideoRef}
                          src={proxyUrl}
                          className="absolute inset-0 m-auto w-full object-contain pointer-events-none"
                          muted
                        />
                      )}
                    </div>
                  ) : (
                    <div className="w-full h-full relative overflow-hidden bg-black">
                      {proxyUrl && (
                        <div
                          className="absolute pointer-events-none transition-transform duration-75 origin-top-left"
                          style={{
                            width: `${(1.0 / activeCrop.w) * 100}%`,
                            height: '100%',
                            left: `${-((activeCrop.cx - activeCrop.w / 2) / activeCrop.w) * 100}%`,
                            top: `${-((activeCrop.cy - activeCrop.h / 2) / activeCrop.h) * 100}%`,
                          }}
                        >
                          <video
                            ref={previewVideoRef}
                            src={proxyUrl}
                            className="w-full h-full object-cover"
                            muted
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Social Platform Safe Zones Overlay */}
                  {showSafeZones && (
                    <div className="absolute inset-0 pointer-events-none flex flex-col justify-between p-2 select-none">
                      {/* Top Header Safe Zone (10%) */}
                      <div className="h-[12%] border-b border-rose-500/40 bg-rose-500/10 flex items-center justify-center">
                        <span className="text-[9px] text-rose-300 font-mono">Header / Profile Zone</span>
                      </div>

                      {/* Right Action Icons (TikTok / Reels) */}
                      <div className="absolute right-2 bottom-20 flex flex-col gap-3 items-center opacity-70">
                        <div className="w-6 h-6 rounded-full bg-slate-700/80 border border-slate-600 flex items-center justify-center text-[10px] text-white">❤️</div>
                        <div className="w-6 h-6 rounded-full bg-slate-700/80 border border-slate-600 flex items-center justify-center text-[10px] text-white">💬</div>
                        <div className="w-6 h-6 rounded-full bg-slate-700/80 border border-slate-600 flex items-center justify-center text-[10px] text-white">↗️</div>
                      </div>

                      {/* Bottom Caption Safe Zone (20%) */}
                      <div className="h-[22%] border-t border-amber-500/40 bg-amber-500/10 flex items-center justify-center">
                        <span className="text-[9px] text-amber-300 font-mono">Caption / Subtitles Area</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Timeline & Controls Toolbar */}
        <div className="bg-slate-900 px-6 py-4 border-t border-slate-800 flex flex-col gap-3">
          {/* Scrubber Strip */}
          <div className="flex items-center gap-3">
            <button
              onClick={togglePlay}
              className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition text-xs font-semibold"
            >
              {isPlaying ? '⏸ Pause' : '▶ Play'}
            </button>

            <span className="text-xs font-mono text-slate-400 min-w-[70px]">
              {((currentTimeMs - clip.start_ms) / 1000).toFixed(1)}s / {((clip.end_ms - clip.start_ms) / 1000).toFixed(1)}s
            </span>

            {/* Slider */}
            <input
              type="range"
              min={clip.start_ms}
              max={clip.end_ms}
              value={currentTimeMs}
              onChange={(e) => {
                const ms = Number(e.target.value);
                setCurrentTimeMs(ms);
                if (videoRef.current) {
                  videoRef.current.currentTime = ms / 1000.0;
                }
              }}
              className="flex-1 accent-indigo-500 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
            />

            <button
              onClick={handleAddKeyframe}
              className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded transition"
            >
              + Add Keyframe
            </button>
          </div>

          {/* Keyframes Indicator Bar */}
          <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800/60">
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">Mode:</span>
              {(['speaker_track', 'balanced', 'center', 'fit_blur'] as ReframeMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => handleModeChange(mode)}
                  className={`px-2.5 py-1 rounded text-xs transition border ${
                    currentMode === mode
                      ? 'bg-indigo-600 text-white border-indigo-500 font-medium'
                      : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
                  }`}
                >
                  {mode.replace('_', ' ')}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <span className="text-slate-500">{keyframes.length} Keyframes</span>
              {reframeData?.has_edits && (
                <button
                  onClick={handleResetToAuto}
                  className="text-xs text-rose-400 hover:text-rose-300 transition underline"
                >
                  Reset to Auto Framing
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
