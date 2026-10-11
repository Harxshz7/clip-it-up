"use client";

import React, { useEffect, useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { api } from "@/lib/api";
import { ClipAlternative } from "@clip-it-up/shared";
import { Bookmark, Sparkles, Check, ArrowRight, Layers, HelpCircle } from "lucide-react";

export const HookTab: React.FC = () => {
  const { doc, setHook, setCurrentTimeMs } = useEditorStore();
  const [alternatives, setAlternatives] = useState<ClipAlternative[]>([]);
  const [loading, setLoading] = useState(false);
  const [includeTitleCard, setIncludeTitleCard] = useState(false);

  const currentHook = doc?.hook || {
    text: "Opening hook line",
    source: "auto",
    start_ms: doc?.range.start_ms || 0,
  };

  useEffect(() => {
    async function loadAlternatives() {
      if (!doc?.clip_id) return;
      try {
        setLoading(true);
        const res = await api.listClipAlternatives(doc.clip_id);
        setAlternatives(res);
      } catch (err) {
        console.error("Failed to load alternatives", err);
      } finally {
        setLoading(false);
      }
    }
    loadAlternatives();
  }, [doc?.clip_id]);

  const handleSelectHook = (alt: ClipAlternative) => {
    setHook({
      text: alt.text,
      source: "alt",
      start_ms: alt.start_ms,
    });
    setCurrentTimeMs(alt.start_ms);
  };

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Bookmark className="w-4 h-4 text-purple-400" />
          Hook Optimizer &amp; Swap
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          First 3 seconds dictate 80% of retention. Select the most compelling opening phrase.
        </p>
      </div>

      {/* Active Hook Card */}
      <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-500/60 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-purple-400" /> Active Hook
          </span>
          <span className="text-[10px] font-mono text-purple-400 bg-purple-900/60 px-1.5 py-0.5 rounded">
            Starts at {(currentHook.start_ms / 1000.0).toFixed(1)}s
          </span>
        </div>
        <p className="font-bold text-white text-sm leading-snug">
          "{currentHook.text}"
        </p>
      </div>

      {/* Narrative Structure Markers: Hook + Body + CTA */}
      <div className="space-y-2 p-3 rounded-xl bg-zinc-900 border border-zinc-800">
        <h4 className="font-semibold text-white flex items-center gap-1.5 text-xs">
          <Layers className="w-3.5 h-3.5 text-purple-400" />
          Clip Narrative Structure
        </h4>
        <div className="grid grid-cols-3 gap-1.5 pt-1 text-center font-mono text-[10px]">
          <div className="p-1.5 rounded bg-purple-900/40 border border-purple-700/50 text-purple-200">
            <span className="font-bold block">Hook (0-4s)</span>
            <span className="text-zinc-400 text-[9px]">High Energy Intro</span>
          </div>
          <div className="p-1.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
            <span className="font-bold block">Body Core</span>
            <span className="text-zinc-400 text-[9px]">Story / Insight</span>
          </div>
          <div className="p-1.5 rounded bg-emerald-950/40 border border-emerald-700/50 text-emerald-300">
            <span className="font-bold block">Payoff / CTA</span>
            <span className="text-zinc-400 text-[9px]">Punchline or Loop</span>
          </div>
        </div>
      </div>

      {/* Alternative Hooks List */}
      <div className="space-y-3 pt-2 border-t border-zinc-800">
        <div className="flex items-center justify-between">
          <h4 className="font-semibold text-white">Alternative Openings ({alternatives.length})</h4>
          {loading && <span className="text-[10px] text-zinc-500">Loading alts...</span>}
        </div>

        {alternatives.length === 0 && !loading ? (
          <p className="text-zinc-500 text-center py-4 text-xs">No alternatives found.</p>
        ) : (
          <div className="space-y-2.5">
            {alternatives.map((alt) => {
              const isCurrent = currentHook.start_ms === alt.start_ms;
              return (
                <div
                  key={alt.id}
                  onClick={() => handleSelectHook(alt)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    isCurrent
                      ? "bg-purple-950/40 border-purple-500 shadow-md"
                      : "bg-zinc-900/80 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-mono text-zinc-400">
                      Starts at {(alt.start_ms / 1000.0).toFixed(1)}s
                    </span>
                    {alt.score && (
                      <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/40">
                        {Math.round(alt.score * 100)}% retention
                      </span>
                    )}
                  </div>
                  <p className="font-bold text-white text-xs mb-1">"{alt.text}"</p>
                  {alt.reason && (
                    <p className="text-[10px] text-zinc-400 leading-normal flex items-start gap-1">
                      <HelpCircle className="w-3 h-3 text-purple-400 shrink-0 mt-0.5" />
                      <span>{alt.reason}</span>
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
