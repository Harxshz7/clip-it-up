"use client";

import React, { useMemo } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { Sparkles, VolumeX, MicOff, Scissors, RotateCcw, Play, Check } from "lucide-react";

export const CleanupTab: React.FC = () => {
  const {
    doc,
    edl,
    setCleanupOptions,
    toggleRemoval,
    removeRemoval,
    setCurrentTimeMs,
  } = useEditorStore();

  const options = doc?.cleanup_options || {
    remove_fillers: true,
    remove_silence: true,
    max_silence_ms: 1500,
    target_silence_ms: 500,
  };

  const removals = doc?.removals || [];
  const enabledRemovals = removals.filter((r) => r.enabled);

  // Calculate saved seconds
  const totalSavedMs = useMemo(() => {
    return enabledRemovals.reduce((sum, r) => sum + Math.max(0, r.end_ms - r.start_ms), 0);
  }, [enabledRemovals]);

  const savedSeconds = (totalSavedMs / 1000.0).toFixed(1);

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-purple-400" />
          Smart Clean-up &amp; Silence Removal
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          Eliminate dead air, awkward pauses, and verbal fillers (um, uh, like)
        </p>
      </div>

      {/* Savings Metric Card */}
      <div className="p-4 rounded-xl bg-purple-950/30 border border-purple-800/40 flex items-center justify-between">
        <div>
          <span className="text-[11px] text-purple-300 font-medium block">Total Saved Time</span>
          <span className="text-2xl font-black text-purple-100">
            {savedSeconds}s <span className="text-xs font-normal text-purple-300">trimmed</span>
          </span>
        </div>
        <div className="text-right">
          <span className="text-[11px] text-zinc-400 font-medium block">Active Cuts</span>
          <span className="text-lg font-bold text-white">{enabledRemovals.length} cuts</span>
        </div>
      </div>

      {/* Toggles */}
      <div className="space-y-3">
        {/* Fillers toggle */}
        <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-2.5">
            <MicOff className="w-4 h-4 text-purple-400" />
            <div>
              <p className="font-medium text-white">Remove Verbal Fillers</p>
              <p className="text-[10px] text-zinc-400">Cuts "um", "uh", "you know", "like"</p>
            </div>
          </div>
          <input
            type="checkbox"
            checked={options.remove_fillers}
            onChange={(e) => setCleanupOptions({ remove_fillers: e.target.checked })}
            className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
          />
        </div>

        {/* Silence toggle */}
        <div className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-2.5">
            <VolumeX className="w-4 h-4 text-purple-400" />
            <div>
              <p className="font-medium text-white">Remove Dead Silence</p>
              <p className="text-[10px] text-zinc-400">Condenses long pauses into natural gaps</p>
            </div>
          </div>
          <input
            type="checkbox"
            checked={options.remove_silence}
            onChange={(e) => setCleanupOptions({ remove_silence: e.target.checked })}
            className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Silence Threshold Slider */}
      {options.remove_silence && (
        <div className="space-y-2 p-3 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex justify-between text-zinc-400 text-[11px]">
            <span>Silence Threshold</span>
            <span className="font-mono text-zinc-200">{(options.max_silence_ms / 1000).toFixed(1)}s</span>
          </div>
          <input
            type="range"
            min="500"
            max="3000"
            step="100"
            value={options.max_silence_ms}
            onChange={(e) => setCleanupOptions({ max_silence_ms: Number(e.target.value) })}
            className="w-full accent-purple-500"
          />
          <p className="text-[10px] text-zinc-500">
            Pauses longer than {(options.max_silence_ms / 1000).toFixed(1)}s will be condensed.
          </p>
        </div>
      )}

      {/* List of Removals */}
      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <h4 className="font-semibold text-white flex items-center justify-between">
          <span>Detected Cuts ({removals.length})</span>
          <span className="text-[10px] font-normal text-zinc-400">Click to seek &bull; Toggle to keep</span>
        </h4>

        {removals.length === 0 ? (
          <p className="text-zinc-500 text-center py-4 text-xs">No cuts detected in this clip.</p>
        ) : (
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {removals.map((r) => {
              const durS = ((r.end_ms - r.start_ms) / 1000.0).toFixed(2);
              return (
                <div
                  key={r.id}
                  className={`p-2 rounded-lg border flex items-center justify-between transition-colors ${
                    r.enabled
                      ? "bg-zinc-900 border-zinc-800"
                      : "bg-zinc-950 border-zinc-900 opacity-50"
                  }`}
                >
                  <div
                    onClick={() => setCurrentTimeMs(r.start_ms)}
                    className="flex-1 cursor-pointer"
                  >
                    <div className="flex items-center gap-1.5 font-medium text-zinc-200">
                      <span className="capitalize text-[11px] font-semibold text-purple-400">
                        {r.kind}
                      </span>
                      <span className="text-[10px] text-zinc-500 font-mono">
                        {(r.start_ms / 1000.0).toFixed(1)}s &rarr; {(r.end_ms / 1000.0).toFixed(1)}s ({durS}s)
                      </span>
                    </div>
                    {r.text && <p className="text-[10px] text-zinc-400 truncate">"{r.text}"</p>}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => toggleRemoval(r.id)}
                      className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                        r.enabled
                          ? "bg-purple-900/50 hover:bg-purple-800 text-purple-200"
                          : "bg-zinc-800 hover:bg-zinc-700 text-zinc-400"
                      }`}
                    >
                      {r.enabled ? "Cut" : "Kept"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
