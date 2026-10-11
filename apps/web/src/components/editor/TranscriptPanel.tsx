"use client";

import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { api } from "@/lib/api";
import { TranscriptWord } from "@clip-it-up/shared";
import {
  Scissors,
  Sparkles,
  Bookmark,
  VolumeX,
  Volume2,
  Trash2,
  RotateCcw,
  Check,
  Edit2,
  AlertCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface TranscriptPanelProps {
  videoId: string;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ videoId }) => {
  const {
    doc,
    currentTimeMs,
    setCurrentTimeMs,
    setRange,
    addManualRemoval,
    toggleRemoval,
    removeRemoval,
    updateWordText,
    toggleWordEmphasis,
    setHook,
  } = useEditorStore();

  const [words, setWords] = useState<TranscriptWord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSpan, setSelectedSpan] = useState<{ startIdx: number; endIdx: number } | null>(null);
  const [editingWordIdx, setEditingWordIdx] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const startMs = doc?.range.start_ms || 0;
  const endMs = doc?.range.end_ms || 10000;
  const durationS = Math.round((endMs - startMs) / 1000);

  // Fetch words with 30s context margin on either side
  useEffect(() => {
    async function loadTranscriptWords() {
      if (!videoId) return;
      try {
        setLoading(true);
        const marginMs = 30000;
        const fromMs = Math.max(0, startMs - marginMs);
        const toMs = endMs + marginMs;
        const res = await api.getTranscriptWords(videoId, { from_ms: fromMs, to_ms: toMs });
        if (res && res.words) {
          setWords(res.words);
        }
      } catch (err) {
        console.error("Failed to load transcript words margin", err);
      } finally {
        setLoading(false);
      }
    }
    loadTranscriptWords();
  }, [videoId, startMs, endMs]);

  // Handle word selection
  const handleWordMouseDown = (idx: number) => {
    setSelectedSpan({ startIdx: idx, endIdx: idx });
  };

  const handleWordMouseEnter = (idx: number, e: React.MouseEvent) => {
    if (e.buttons === 1 && selectedSpan) {
      setSelectedSpan({
        startIdx: Math.min(selectedSpan.startIdx, idx),
        endIdx: Math.max(selectedSpan.startIdx, idx),
      });
    }
  };

  const clearSelection = useCallback(() => {
    setSelectedSpan(null);
  }, []);

  // Check if a word or span is inside a removal
  const getRemovalForWord = (w: TranscriptWord) => {
    if (!doc || !doc.removals) return null;
    return doc.removals.find(
      (r) => r.enabled && r.start_ms <= w.start_ms && w.end_ms <= r.end_ms
    );
  };

  // Perform actions on selected word span
  const handleDeleteSelected = () => {
    if (!selectedSpan || words.length === 0) return;
    const sWord = words[selectedSpan.startIdx];
    const eWord = words[selectedSpan.endIdx];
    const text = words
      .slice(selectedSpan.startIdx, selectedSpan.endIdx + 1)
      .map((w) => w.word)
      .join(" ");

    addManualRemoval({
      start_ms: sWord.start_ms,
      end_ms: eWord.end_ms,
      text,
    });
    clearSelection();
  };

  const handleTrimStartHere = () => {
    if (!selectedSpan || words.length === 0) return;
    const sWord = words[selectedSpan.startIdx];
    if (sWord.start_ms < endMs - 2000) {
      setRange({ start_ms: sWord.start_ms, end_ms: endMs });
    }
    clearSelection();
  };

  const handleTrimEndHere = () => {
    if (!selectedSpan || words.length === 0) return;
    const eWord = words[selectedSpan.endIdx];
    if (eWord.end_ms > startMs + 2000) {
      setRange({ start_ms: startMs, end_ms: eWord.end_ms });
    }
    clearSelection();
  };

  const handleMakeHook = () => {
    if (!selectedSpan || words.length === 0) return;
    const sWord = words[selectedSpan.startIdx];
    const text = words
      .slice(selectedSpan.startIdx, selectedSpan.endIdx + 1)
      .map((w) => w.word)
      .join(" ");

    setHook({
      text,
      source: "manual",
      start_ms: sWord.start_ms,
    });
    clearSelection();
  };

  const handleHighlight = () => {
    if (!selectedSpan || !doc) return;
    const sWord = words[selectedSpan.startIdx];
    const eWord = words[selectedSpan.endIdx];

    // Find corresponding captions words
    doc.captions.words.forEach((cw, idx) => {
      if (cw.start_ms >= sWord.start_ms && cw.end_ms <= eWord.end_ms) {
        toggleWordEmphasis(idx);
      }
    });
    clearSelection();
  };

  const handleSaveWordEdit = (wordIdxInCaption: number) => {
    if (editText.trim()) {
      updateWordText(wordIdxInCaption, editText.trim());
    }
    setEditingWordIdx(null);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-xl select-none">
      {/* Top status bar with length warnings */}
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-950 border-b border-zinc-800 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white">Transcript Editor</span>
          <span className="text-[11px] font-mono text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
            {durationS}s duration
          </span>
          {durationS > 60 && (
            <span className="flex items-center gap-1 text-[11px] text-amber-400 bg-amber-950/60 border border-amber-800/60 px-1.5 py-0.5 rounded">
              <AlertCircle className="w-3 h-3" />
              TikTok &gt;60s limit warning
            </span>
          )}
        </div>

        <span className="text-[11px] text-zinc-400">
          Drag to select &bull; Click to seek
        </span>
      </div>

      {/* Floating selection action bar */}
      {selectedSpan && (
        <div className="bg-purple-950/90 border-b border-purple-700/60 px-3 py-2 flex items-center justify-between text-xs animate-in fade-in">
          <span className="text-purple-200 font-medium">
            {selectedSpan.endIdx - selectedSpan.startIdx + 1} words selected
          </span>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1 px-2 py-1 rounded bg-red-600/80 hover:bg-red-600 text-white font-medium transition-colors"
              title="Cut out these words"
            >
              <Trash2 className="w-3 h-3" />
              <span>Delete</span>
            </button>

            <button
              onClick={handleTrimStartHere}
              className="flex items-center gap-1 px-2 py-1 rounded bg-purple-700 hover:bg-purple-600 text-white font-medium transition-colors"
            >
              <Scissors className="w-3 h-3" />
              <span>Trim Start Here</span>
            </button>

            <button
              onClick={handleTrimEndHere}
              className="flex items-center gap-1 px-2 py-1 rounded bg-purple-700 hover:bg-purple-600 text-white font-medium transition-colors"
            >
              <Scissors className="w-3 h-3" />
              <span>Trim End Here</span>
            </button>

            <button
              onClick={handleHighlight}
              className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-emerald-300 font-medium transition-colors"
            >
              <Sparkles className="w-3 h-3" />
              <span>Highlight</span>
            </button>

            <button
              onClick={handleMakeHook}
              className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-yellow-300 font-medium transition-colors"
            >
              <Bookmark className="w-3 h-3" />
              <span>Make Hook</span>
            </button>

            <button
              onClick={clearSelection}
              className="px-1.5 py-1 text-zinc-400 hover:text-white"
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* Transcript Words Stream Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {loading && words.length === 0 ? (
          <div className="flex items-center justify-center h-48 text-zinc-500 text-xs">
            <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mr-2" />
            Loading transcript...
          </div>
        ) : (
          <div className="leading-relaxed flex flex-wrap gap-x-1.5 gap-y-2 text-sm">
            {words.map((w, idx) => {
              const isInsideClip = w.start_ms >= startMs && w.end_ms <= endMs;
              const isCurrent = currentTimeMs >= w.start_ms && currentTimeMs <= w.end_ms;
              const removal = getRemovalForWord(w);
              const isSelected =
                selectedSpan &&
                idx >= selectedSpan.startIdx &&
                idx <= selectedSpan.endIdx;

              // Check if word has emphasis in doc
              const captionWordIdx = doc?.captions.words.findIndex(
                (cw) => cw.start_ms === w.start_ms
              );
              const isEmphasized =
                captionWordIdx !== undefined &&
                captionWordIdx >= 0 &&
                doc?.captions.words[captionWordIdx]?.emphasis;

              return (
                <span
                  key={idx}
                  onMouseDown={() => handleWordMouseDown(idx)}
                  onMouseEnter={(e) => handleWordMouseEnter(idx, e)}
                  onClick={(e) => {
                    e.stopPropagation();
                    setCurrentTimeMs(w.start_ms);
                  }}
                  className={`relative group inline-flex items-center px-1 py-0.5 rounded cursor-pointer transition-all duration-75 ${
                    !isInsideClip
                      ? "opacity-35 text-zinc-500 hover:opacity-75"
                      : removal
                      ? "line-through text-red-400/80 bg-red-950/20"
                      : isSelected
                      ? "bg-purple-600 text-white font-medium"
                      : isCurrent
                      ? "bg-yellow-400 text-black font-bold shadow-md scale-105"
                      : isEmphasized
                      ? "text-emerald-400 font-semibold"
                      : "text-zinc-200 hover:bg-zinc-800 hover:text-white"
                  }`}
                  title={`${(w.start_ms / 1000).toFixed(1)}s - ${(w.end_ms / 1000).toFixed(1)}s`}
                >
                  {/* Inline word text or editing input */}
                  {editingWordIdx === captionWordIdx ? (
                    <span className="inline-flex items-center gap-1 z-30">
                      <input
                        type="text"
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveWordEdit(captionWordIdx!);
                          if (e.key === "Escape") setEditingWordIdx(null);
                        }}
                        autoFocus
                        className="bg-black border border-purple-500 text-white text-xs px-1 rounded w-20 outline-none"
                      />
                      <button
                        onClick={() => handleSaveWordEdit(captionWordIdx!)}
                        className="text-emerald-400 hover:text-emerald-300"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                    </span>
                  ) : (
                    <span>{w.word}</span>
                  )}

                  {/* Removal inline indicator chip with undo */}
                  {removal && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleRemoval(removal.id);
                      }}
                      className="ml-1 text-[9px] bg-red-900/60 hover:bg-red-800 text-red-200 px-1 rounded inline-flex items-center gap-0.5"
                      title="Undo cut"
                    >
                      <RotateCcw className="w-2.5 h-2.5" />
                    </button>
                  )}

                  {/* Quick edit button on hover */}
                  {isInsideClip && !removal && captionWordIdx !== undefined && captionWordIdx >= 0 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingWordIdx(captionWordIdx);
                        setEditText(w.word);
                      }}
                      className="opacity-0 group-hover:opacity-100 ml-0.5 p-0.5 text-zinc-400 hover:text-purple-300 transition-opacity"
                      title="Fix caption typo"
                    >
                      <Edit2 className="w-2.5 h-2.5" />
                    </button>
                  )}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Summary Bar */}
      <div className="px-4 py-2 bg-zinc-950 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-400">
        <div className="flex items-center gap-3">
          <span>
            Clip Range: <strong className="text-zinc-200">{(startMs / 1000).toFixed(1)}s</strong> &rarr;{" "}
            <strong className="text-zinc-200">{(endMs / 1000).toFixed(1)}s</strong>
          </span>
          {doc?.removals && doc.removals.length > 0 && (
            <span className="text-red-400">
              {doc.removals.filter((r) => r.enabled).length} cuts applied
            </span>
          )}
        </div>

        <span className="text-[11px] text-zinc-500">
          Source milliseconds: {startMs}ms - {endMs}ms
        </span>
      </div>
    </div>
  );
};
