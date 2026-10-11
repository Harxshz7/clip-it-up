"use client";

import React, { useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { Crop, Shield, AlertTriangle, RotateCcw, Check, UserCheck } from "lucide-react";

const MODES = [
  { key: "speaker_track", label: "Speaker Track", desc: "Dynamically tracks active speaker head position" },
  { key: "balanced", label: "Balanced", desc: "Smooth framing between 2 speakers with smooth pan" },
  { key: "center", label: "Center Fixed", desc: "Fixed 9:16 center crop (classic vertical cut)" },
  { key: "fit_blur", label: "Fit & Blur", desc: "Entire 16:9 frame with blurred vertical background" },
];

export const FramingTab: React.FC = () => {
  const {
    doc,
    showSafeZone,
    setShowSafeZone,
    setReframeModeOverride,
    setReframeKeyframes,
  } = useEditorStore();

  const [hasFaceCutWarning, setHasFaceCutWarning] = useState(false);
  const activeMode = doc?.reframe.mode_overrides?.default || "speaker_track";

  const handleApplySuggestedFix = () => {
    // Switch to balanced or center
    setReframeModeOverride("default", "balanced");
    setHasFaceCutWarning(false);
  };

  const handleResetToAuto = () => {
    setReframeModeOverride("default", "speaker_track");
    setReframeKeyframes([]);
  };

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Crop className="w-4 h-4 text-purple-400" />
          Vertical 9:16 Framing
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          Smart framing and face tracking AI for vertical video platforms
        </p>
      </div>

      {/* Suggested Fix Alert Chip */}
      {hasFaceCutWarning && (
        <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-600/50 flex items-start gap-2.5 text-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1.5">
            <p className="font-medium text-xs">Low tracking confidence near boundary</p>
            <p className="text-[11px] text-amber-300/80">
              Face is near crop edge. Switching to Balanced mode prevents head clipping.
            </p>
            <button
              onClick={handleApplySuggestedFix}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs rounded transition-colors"
            >
              Apply Suggested Fix (Balanced)
            </button>
          </div>
        </div>
      )}

      {/* Framing Modes */}
      <div className="space-y-3">
        <h4 className="font-semibold text-white">Tracking Mode</h4>
        <div className="space-y-2">
          {MODES.map((m) => {
            const isSelected = activeMode === m.key;
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
                  <span className="font-bold text-white text-sm flex items-center gap-1.5">
                    {m.label}
                    {isSelected && <Check className="w-3.5 h-3.5 text-purple-400" />}
                  </span>
                </div>
                <p className="text-[11px] text-zinc-400">{m.desc}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Safe Zone Toggle */}
      <div className="pt-2 border-t border-zinc-800 space-y-3">
        <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-purple-400" />
            <div>
              <p className="font-medium text-white">Platform Safe Zones</p>
              <p className="text-[10px] text-zinc-400">Avoid UI overlap on TikTok &amp; Reels</p>
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
