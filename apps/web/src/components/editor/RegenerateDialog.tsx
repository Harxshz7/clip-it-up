"use client";

import React, { useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { api } from "@/lib/api";
import { ClipAlternative } from "@clip-it-up/shared";
import { Sparkles, RefreshCw, Check, ArrowRight, X, Clock, Scissors, Bookmark, Compass } from "lucide-react";

interface RegenerateDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const RegenerateDialog: React.FC<RegenerateDialogProps> = ({ isOpen, onClose }) => {
  const { doc, setRange, setHook } = useEditorStore();
  const [mode, setMode] = useState<"length" | "hook" | "trim" | "similar">("length");
  const [targetLength, setTargetLength] = useState<number>(30);
  const [tightness, setTightness] = useState<"tight" | "loose">("tight");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedResult, setGeneratedResult] = useState<ClipAlternative | null>(null);

  if (!isOpen || !doc) return null;

  const handleStartRegenerate = async () => {
    try {
      setIsGenerating(true);
      setGeneratedResult(null);

      const params: Record<string, any> = {};
      if (mode === "length") params.length_s = targetLength;
      if (mode === "trim") params.tightness = tightness;

      const res = await api.regenerateClip(doc.clip_id, { mode, params });
      setGeneratedResult(res.alternative);
    } catch (err) {
      console.error("Regeneration failed", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApplyResult = () => {
    if (!generatedResult) return;
    if (generatedResult.kind === "range") {
      setRange({ start_ms: generatedResult.start_ms, end_ms: generatedResult.end_ms });
    } else if (generatedResult.kind === "hook") {
      setHook({
        text: generatedResult.text,
        source: "alt",
        start_ms: generatedResult.start_ms,
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-400" />
            <h3 className="font-bold text-white text-base">Regenerate Clip</h3>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5 text-xs text-zinc-300">
          {!generatedResult ? (
            <>
              <p className="text-zinc-400">
                Explore alternative variations without re-transcribing. Your existing work is safe: regenerations never overwrite until you click "Use this".
              </p>

              {/* Mode Selection */}
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => setMode("length")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    mode === "length"
                      ? "bg-purple-950/60 border-purple-500 text-white shadow-md"
                      : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 text-zinc-400"
                  }`}
                >
                  <Clock className="w-4 h-4 text-purple-400 mb-1" />
                  <span className="font-bold text-sm block text-white">Target Duration</span>
                  <span className="text-[11px]">Trim to 15s, 30s, 45s, or 60s</span>
                </button>

                <button
                  type="button"
                  onClick={() => setMode("hook")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    mode === "hook"
                      ? "bg-purple-950/60 border-purple-500 text-white shadow-md"
                      : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 text-zinc-400"
                  }`}
                >
                  <Bookmark className="w-4 h-4 text-purple-400 mb-1" />
                  <span className="font-bold text-sm block text-white">Different Hook</span>
                  <span className="text-[11px]">Discover alternative opening line</span>
                </button>

                <button
                  type="button"
                  onClick={() => setMode("trim")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    mode === "trim"
                      ? "bg-purple-950/60 border-purple-500 text-white shadow-md"
                      : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 text-zinc-400"
                  }`}
                >
                  <Scissors className="w-4 h-4 text-purple-400 mb-1" />
                  <span className="font-bold text-sm block text-white">Tighter / Looser Trim</span>
                  <span className="text-[11px]">Fine sentence pacing trim</span>
                </button>

                <button
                  type="button"
                  onClick={() => setMode("similar")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    mode === "similar"
                      ? "bg-purple-950/60 border-purple-500 text-white shadow-md"
                      : "bg-zinc-950/60 border-zinc-800 hover:border-zinc-700 text-zinc-400"
                  }`}
                >
                  <Compass className="w-4 h-4 text-purple-400 mb-1" />
                  <span className="font-bold text-sm block text-white">Find Another Moment</span>
                  <span className="text-[11px]">Similar high-energy conversation</span>
                </button>
              </div>

              {/* Mode Specific Config */}
              {mode === "length" && (
                <div className="space-y-2 pt-2">
                  <span className="text-zinc-300 font-semibold block">Select target length:</span>
                  <div className="flex gap-2">
                    {[15, 30, 45, 60].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setTargetLength(s)}
                        className={`flex-1 py-2 rounded-lg border font-mono font-bold text-xs transition-colors ${
                          targetLength === s
                            ? "bg-purple-600 border-purple-500 text-white"
                            : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white"
                        }`}
                      >
                        {s}s
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {mode === "trim" && (
                <div className="space-y-2 pt-2">
                  <span className="text-zinc-300 font-semibold block">Boundary style:</span>
                  <div className="flex gap-2">
                    {(["tight", "loose"] as const).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setTightness(t)}
                        className={`flex-1 py-2 rounded-lg border capitalize font-semibold text-xs transition-colors ${
                          tightness === t
                            ? "bg-purple-600 border-purple-500 text-white"
                            : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            /* Result comparison */
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-purple-950/40 border border-purple-500/60 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-purple-300 block">
                  Regenerated Alternative
                </span>
                <p className="font-bold text-white text-sm leading-snug">
                  "{generatedResult.text}"
                </p>
                <div className="flex items-center gap-3 text-[11px] text-zinc-400 font-mono pt-1">
                  <span>
                    Range: {(generatedResult.start_ms / 1000).toFixed(1)}s &rarr;{" "}
                    {(generatedResult.end_ms / 1000).toFixed(1)}s
                  </span>
                  {generatedResult.score && (
                    <span className="text-emerald-400 font-bold">
                      {Math.round(generatedResult.score * 100)}% score
                    </span>
                  )}
                </div>
                {generatedResult.reason && (
                  <p className="text-[11px] text-zinc-400 italic">{generatedResult.reason}</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3.5 bg-zinc-950 border-t border-zinc-800 flex items-center justify-end gap-2">
          {!generatedResult ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleStartRegenerate}
                disabled={isGenerating}
                className="px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Regenerating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    Generate Alternative
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setGeneratedResult(null)}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium text-xs transition-colors"
              >
                Keep Mine
              </button>
              <button
                type="button"
                onClick={handleApplyResult}
                className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition-colors"
              >
                <Check className="w-3.5 h-3.5" />
                Use This Alternative
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
