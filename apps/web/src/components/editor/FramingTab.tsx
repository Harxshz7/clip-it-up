"use client";

import React, { useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import {
  Crop,
  Shield,
  AlertTriangle,
  RotateCcw,
  Check,
  Users,
  Maximize,
  Layers,
  LayoutTemplate,
  Tv,
  Eye,
  Sliders,
} from "lucide-react";
import { ReframeMode } from "@clip-it-up/shared";

interface FramingModeItem {
  key: ReframeMode;
  label: string;
  badge?: string;
  desc: string;
  icon: React.ElementType;
}

const MODES: FramingModeItem[] = [
  {
    key: "speaker_track",
    label: "Speaker Track",
    badge: "Auto",
    desc: "Dynamically tracks active speaker with look-room and anti-ping-pong",
    icon: Crop,
  },
  {
    key: "balanced",
    label: "Balanced",
    badge: "2-Shot",
    desc: "Smooth framing centered between 2 participants",
    icon: Users,
  },
  {
    key: "split_stack",
    label: "Split Stack",
    badge: "Panel",
    desc: "2 stacked 1080x960 frames framing both active participants",
    icon: Layers,
  },
  {
    key: "content_fit",
    label: "Content Fit",
    badge: "Slides",
    desc: "Full 16:9 content scaled to width on blurred or brand background",
    icon: Maximize,
  },
  {
    key: "content_zoom",
    label: "Content Zoom",
    badge: "ROI",
    desc: "Smart pan & zoom into active window/code editor with text readability guard",
    icon: Eye,
  },
  {
    key: "stack",
    label: "Stack (60/40)",
    badge: "Hybrid",
    desc: "Content on top (60%), speaker face cutout below (40%)",
    icon: LayoutTemplate,
  },
  {
    key: "pip",
    label: "PIP (Picture-in-Picture)",
    badge: "Demo",
    desc: "Content full-frame with speaker video thumbnail in safe corner",
    icon: Tv,
  },
  {
    key: "center",
    label: "Center Fixed",
    desc: "Fixed 9:16 center crop (classic vertical cut)",
    icon: Crop,
  },
  {
    key: "fit_blur",
    label: "Fit & Blur (v1)",
    desc: "Original fallback fit on blurred vertical canvas",
    icon: Maximize,
  },
];

export const FramingTab: React.FC = () => {
  const {
    doc,
    showSafeZone,
    setShowSafeZone,
    setReframeModeOverride,
    setReframeKeyframes,
  } = useEditorStore();

  const [activeWarning, setActiveWarning] = useState<
    "unreadable_text" | "face_cut_risk" | "multi_speaker_conflict" | null
  >(null);

  const [selectedSpeaker, setSelectedSpeaker] = useState<string>("auto");
  const [roiX, setRoiX] = useState<number>(0.10);
  const [roiY, setRoiY] = useState<number>(0.10);
  const [roiW, setRoiW] = useState<number>(0.60);
  const [roiH, setRoiH] = useState<number>(0.75);

  const activeMode = (doc?.reframe?.mode_overrides?.default as ReframeMode) || "speaker_track";

  const handleApplyWarningFix = (targetMode: ReframeMode) => {
    setReframeModeOverride("default", targetMode);
    setActiveWarning(null);
  };

  const handleResetToAuto = () => {
    setReframeModeOverride("default", "speaker_track");
    setReframeKeyframes([]);
    setSelectedSpeaker("auto");
    setActiveWarning(null);
  };

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Crop className="w-4 h-4 text-purple-400" />
          Vertical 9:16 Framing &amp; Layouts
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          Phase 7b content-aware framing: multi-person panels, slides, demos, and split screens.
        </p>
      </div>

      {/* Warning Chips with One-Click Fixes */}
      {activeWarning === "unreadable_text" && (
        <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-600/50 flex items-start gap-2.5 text-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1.5">
            <p className="font-medium text-xs">Unreadable Text Warning</p>
            <p className="text-[11px] text-amber-300/80">
              Font size in current zoom is below the 14px mobile readability threshold.
            </p>
            <button
              onClick={() => handleApplyWarningFix("content_fit")}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs rounded transition-colors"
            >
              Switch to Content Fit (Recommended)
            </button>
          </div>
        </div>
      )}

      {activeWarning === "face_cut_risk" && (
        <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-600/50 flex items-start gap-2.5 text-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1.5">
            <p className="font-medium text-xs">Face Boundary Alert</p>
            <p className="text-[11px] text-amber-300/80">
              Participant face is close to horizontal crop edge.
            </p>
            <button
              onClick={() => handleApplyWarningFix("balanced")}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs rounded transition-colors"
            >
              Switch to Balanced Framing
            </button>
          </div>
        </div>
      )}

      {/* Speaker Follow Selector */}
      <div className="space-y-2">
        <label className="font-semibold text-white flex items-center gap-1.5">
          <Users className="w-3.5 h-3.5 text-purple-400" />
          Target Speaker / Focus Track
        </label>
        <div className="grid grid-cols-4 gap-1.5">
          {["auto", "SPEAKER_00", "SPEAKER_01", "SPEAKER_02"].map((spk) => {
            const isSelected = selectedSpeaker === spk;
            return (
              <button
                key={spk}
                onClick={() => setSelectedSpeaker(spk)}
                className={`py-1.5 px-2 rounded-lg border text-[11px] font-medium transition-all ${
                  isSelected
                    ? "bg-purple-900/60 border-purple-500 text-white"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-white"
                }`}
              >
                {spk === "auto" ? "AI Auto" : spk.replace("SPEAKER_", "Spk ")}
              </button>
            );
          })}
        </div>
      </div>

      {/* Framing Modes Selection */}
      <div className="space-y-3">
        <h4 className="font-semibold text-white flex items-center justify-between">
          <span>Framing &amp; Layout Mode</span>
          <span className="text-[10px] text-purple-400 font-mono uppercase">{activeMode}</span>
        </h4>
        <div className="space-y-2">
          {MODES.map((m) => {
            const isSelected = activeMode === m.key;
            const Icon = m.icon;
            return (
              <div
                key={m.key}
                onClick={() => setReframeModeOverride("default", m.key)}
                className={`p-3 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? "bg-purple-950/40 border-purple-500 shadow-md shadow-purple-900/20"
                    : "bg-zinc-900/80 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-white text-sm flex items-center gap-2">
                    <Icon className={`w-4 h-4 ${isSelected ? "text-purple-400" : "text-zinc-400"}`} />
                    {m.label}
                    {m.badge && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-900/60 text-purple-300 font-mono">
                        {m.badge}
                      </span>
                    )}
                  </span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-purple-400" />}
                </div>
                <p className="text-[11px] text-zinc-400 pl-6">{m.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Content Zoom ROI Controls */}
      {activeMode === "content_zoom" && (
        <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
          <div className="flex items-center gap-1.5 font-semibold text-white">
            <Sliders className="w-3.5 h-3.5 text-purple-400" />
            <span>Region of Interest (ROI) Boundaries</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div>
              <span className="text-zinc-400">ROI X ({Math.round(roiX * 100)}%)</span>
              <input
                type="range"
                min="0"
                max="0.8"
                step="0.05"
                value={roiX}
                onChange={(e) => setRoiX(parseFloat(e.target.value))}
                className="w-full accent-purple-500"
              />
            </div>
            <div>
              <span className="text-zinc-400">ROI Y ({Math.round(roiY * 100)}%)</span>
              <input
                type="range"
                min="0"
                max="0.8"
                step="0.05"
                value={roiY}
                onChange={(e) => setRoiY(parseFloat(e.target.value))}
                className="w-full accent-purple-500"
              />
            </div>
            <div>
              <span className="text-zinc-400">Width ({Math.round(roiW * 100)}%)</span>
              <input
                type="range"
                min="0.2"
                max="1.0"
                step="0.05"
                value={roiW}
                onChange={(e) => setRoiW(parseFloat(e.target.value))}
                className="w-full accent-purple-500"
              />
            </div>
            <div>
              <span className="text-zinc-400">Height ({Math.round(roiH * 100)}%)</span>
              <input
                type="range"
                min="0.2"
                max="1.0"
                step="0.05"
                value={roiH}
                onChange={(e) => setRoiH(parseFloat(e.target.value))}
                className="w-full accent-purple-500"
              />
            </div>
          </div>
        </div>
      )}

      {/* Safe Zone Toggle */}
      <div className="pt-2 border-t border-zinc-800 space-y-3">
        <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-purple-400" />
            <div>
              <p className="font-medium text-white">Platform Safe Zones</p>
              <p className="text-[10px] text-zinc-400">Avoid UI &amp; Caption overlaps on TikTok, Reels, Shorts</p>
            </div>
          </div>
          <input
            type="checkbox"
            checked={showSafeZone}
            onChange={(e) => setShowSafeZone(e.target.checked)}
            className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
          />
        </div>

        {/* Reset button */}
        <button
          onClick={handleResetToAuto}
          className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors text-xs font-medium"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Framing to AI Auto</span>
        </button>
      </div>
    </div>
  );
};
