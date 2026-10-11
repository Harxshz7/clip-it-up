"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useEditorStore, EditorTab } from "@/lib/editorStore";
import { Video } from "@clip-it-up/shared";
import { EditorPreview } from "@/components/editor/EditorPreview";
import { TranscriptPanel } from "@/components/editor/TranscriptPanel";
import { CaptionsTab } from "@/components/editor/CaptionsTab";
import { FramingTab } from "@/components/editor/FramingTab";
import { CleanupTab } from "@/components/editor/CleanupTab";
import { HookTab } from "@/components/editor/HookTab";
import { ExportTab } from "@/components/editor/ExportTab";
import { ConflictDialog } from "@/components/editor/ConflictDialog";
import { DraftRecoveryBanner } from "@/components/editor/DraftRecoveryBanner";
import { RegenerateDialog } from "@/components/editor/RegenerateDialog";

import {
  ArrowLeft,
  Undo2,
  Redo2,
  Bookmark,
  Sparkles,
  Crop,
  Download,
  Scissors,
  CheckCircle2,
  Clock,
  RotateCcw,
  AlertCircle,
  Loader2,
  Save,
  Layers,
} from "lucide-react";

export default function ClipEditorPage() {
  const params = useParams();
  const router = useRouter();
  const videoId = params.id as string;
  const clipId = params.clipId as string;

  const [video, setVideo] = useState<Video | null>(null);
  const [proxyUrl, setProxyUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRegenerateOpen, setIsRegenerateOpen] = useState(false);
  const [reframeAnalyzing, setReframeAnalyzing] = useState(false);

  const {
    doc,
    edl,
    serverVersion,
    isDirty,
    saveStatus,
    saveError,
    activeTab,
    setActiveTab,
    init,
    undo,
    redo,
    canUndo,
    canRedo,
    save,
    resetToAuto,
    setCleanupOptions,
  } = useEditorStore();

  // 1. Initial Load of Video, Proxy, and Clip Edit Doc
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [videoData, proxyRes, editRecord] = await Promise.all([
          api.getVideo(videoId),
          api.getProxyUrl(videoId).catch(() => null),
          api.getClipEdit(clipId),
        ]);

        setVideo(videoData);
        if (proxyRes?.proxy_url) {
          setProxyUrl(proxyRes.proxy_url);
        }

        init(editRecord);

        // Check if reframe keyframes exist yet (progressive editing)
        if (!editRecord.doc.reframe.keyframes || editRecord.doc.reframe.keyframes.length === 0) {
          setReframeAnalyzing(true);
        }
      } catch (err) {
        console.error("Failed to load editor data", err);
      } finally {
        setLoading(false);
      }
    }

    if (videoId && clipId) {
      loadData();
    }
  }, [videoId, clipId, init]);

  // 2. BeforeUnload Guard for unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved changes in the clip editor.";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // 3. SSE Progressive Editing: listen for reframe_ready and export_progress
  useEffect(() => {
    if (!videoId) return;
    const sseUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/jobs/stream?video_id=${videoId}`;
    let eventSource: EventSource | null = null;

    try {
      eventSource = new EventSource(sseUrl);
      eventSource.addEventListener("reframe_ready", (e: any) => {
        setReframeAnalyzing(false);
      });
    } catch {}

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [videoId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[75vh] space-y-4">
        <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
        <span className="text-zinc-400 font-medium text-sm">Opening Studio Clip Editor...</span>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="p-8 text-center text-zinc-400">
        <p>Clip edit state not found.</p>
        <Link href={`/videos/${videoId}/clips`} className="text-purple-400 underline text-sm mt-2 inline-block">
          Return to clips grid
        </Link>
      </div>
    );
  }

  const durationS = Math.round((doc.range.end_ms - doc.range.start_ms) / 1000);

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-zinc-950 text-white overflow-hidden select-none">
      {/* Top Studio Action Bar */}
      <header className="px-4 py-2.5 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href={`/videos/${videoId}/clips`}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors py-1 px-2 rounded-lg hover:bg-zinc-800"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Clips Grid</span>
          </Link>

          <div className="h-4 w-px bg-zinc-700" />

          <div>
            <h1 className="font-bold text-sm text-white truncate max-w-xs md:max-w-md">
              {doc.hook.text || "Clip Editor"}
            </h1>
            <span className="text-[10px] text-zinc-400 font-mono">
              Version {serverVersion} &bull; {durationS}s &bull; {video?.original_filename}
            </span>
          </div>
        </div>

        {/* Center: Save status & Quick Tools */}
        <div className="flex items-center gap-2">
          {/* Save Status Chip */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border">
            {saveStatus === "saving" && (
              <span className="flex items-center gap-1 text-purple-400 border-purple-800 bg-purple-950/60">
                <Loader2 className="w-3 h-3 animate-spin" /> Saving...
              </span>
            )}
            {saveStatus === "saved" && !isDirty && (
              <span className="flex items-center gap-1 text-emerald-400 border-emerald-800 bg-emerald-950/40">
                <CheckCircle2 className="w-3 h-3" /> Saved
              </span>
            )}
            {isDirty && (
              <span className="flex items-center gap-1 text-amber-400 border-amber-800 bg-amber-950/40">
                <Clock className="w-3 h-3" /> Unsaved draft
              </span>
            )}
            {saveStatus === "error" && (
              <span className="flex items-center gap-1 text-red-400 border-red-800 bg-red-950/40">
                <AlertCircle className="w-3 h-3" /> Save failed
              </span>
            )}
          </div>

          {/* Undo / Redo */}
          <div className="flex items-center bg-zinc-800 rounded-lg p-0.5 border border-zinc-700">
            <button
              onClick={undo}
              disabled={!canUndo()}
              className="p-1.5 text-zinc-300 hover:text-white disabled:opacity-30 transition-opacity"
              title="Undo (Ctrl+Z)"
            >
              <Undo2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={redo}
              disabled={!canRedo()}
              className="p-1.5 text-zinc-300 hover:text-white disabled:opacity-30 transition-opacity"
              title="Redo (Ctrl+Shift+Z)"
            >
              <Redo2 className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Quick One-Click Cleanup Toggle */}
          <button
            onClick={() =>
              setCleanupOptions({
                remove_fillers: !doc.cleanup_options.remove_fillers,
                remove_silence: !doc.cleanup_options.remove_silence,
              })
            }
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              doc.cleanup_options.remove_fillers && doc.cleanup_options.remove_silence
                ? "bg-purple-950/60 text-purple-200 border-purple-600"
                : "bg-zinc-800 text-zinc-400 border-zinc-700 hover:text-white"
            }`}
            title="Toggle filler and silence cuts"
          >
            <Scissors className="w-3.5 h-3.5" />
            <span>AI Clean-up</span>
          </button>

          {/* Regenerate modal trigger */}
          <button
            onClick={() => setIsRegenerateOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-xs font-semibold text-zinc-200 hover:text-white transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Regenerate</span>
          </button>

          {/* Checkpoint Force Save */}
          <button
            onClick={() => save(true, "manual_checkpoint")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shadow-md transition-colors"
            title="Save version checkpoint (Ctrl+S)"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Checkpoint</span>
          </button>
        </div>
      </header>

      {/* Progressive Banner if Reframe or Audio is still analyzing */}
      {reframeAnalyzing && (
        <div className="bg-purple-950/50 border-b border-purple-800/60 px-4 py-1.5 flex items-center justify-between text-xs text-purple-200">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
            <span>
              Analyzing auto-framing in background... preview is currently using center crop fallback and will upgrade automatically without losing edits.
            </span>
          </div>
        </div>
      )}

      {/* Draft Recovery Banner */}
      <div className="p-2 empty:hidden">
        <DraftRecoveryBanner />
      </div>

      {/* Main 3-Column Studio Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 p-3 overflow-hidden min-h-0">
        {/* Left: Transcript Panel (col-span-4) */}
        <div className="lg:col-span-4 h-full min-h-0">
          <TranscriptPanel videoId={videoId} />
        </div>

        {/* Center: 9:16 Preview + Transport (col-span-4) */}
        <div className="lg:col-span-4 h-full min-h-0 flex flex-col">
          <EditorPreview
            proxyUrl={proxyUrl}
            videoTitle={video?.original_filename}
            onCheckpoint={() => save(true, "manual_checkpoint")}
          />
        </div>

        {/* Right: Inspector Tabs Panel (col-span-4) */}
        <div className="lg:col-span-4 h-full min-h-0 flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-xl">
          {/* Tab Navigation Strip */}
          <div className="flex items-center justify-between bg-zinc-950 border-b border-zinc-800 px-2 py-1.5 text-xs font-semibold overflow-x-auto shrink-0">
            {(
              [
                { id: "captions", label: "Captions", icon: Sparkles },
                { id: "framing", label: "Framing", icon: Crop },
                { id: "cleanup", label: "Clean-up", icon: Scissors },
                { id: "hook", label: "Hook", icon: Bookmark },
                { id: "export", label: "Export", icon: Download },
              ] as const
            ).map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as EditorTab)}
                  className={`flex items-center gap-1 px-3 py-1.5 rounded-lg transition-all ${
                    isActive
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Active Tab Body */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === "captions" && <CaptionsTab />}
            {activeTab === "framing" && <FramingTab />}
            {activeTab === "cleanup" && <CleanupTab />}
            {activeTab === "hook" && <HookTab />}
            {activeTab === "export" && <ExportTab />}
          </div>
        </div>
      </div>

      {/* Bottom Compact EDL Timeline Strip */}
      <div className="px-4 py-2 bg-zinc-950 border-t border-zinc-800 flex items-center gap-3 text-xs shrink-0">
        <span className="font-mono text-zinc-400 text-[11px] shrink-0 flex items-center gap-1">
          <Layers className="w-3.5 h-3.5 text-purple-400" />
          EDL Output Timeline:
        </span>
        <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden flex relative">
          {edl?.keep_segments && edl.keep_segments.length > 0 ? (
            edl.keep_segments.map((seg, i) => {
              const totalOut = Math.max(1, edl.total_out_duration_ms);
              const widthPct = (seg.duration_ms / totalOut) * 100;
              return (
                <div
                  key={i}
                  style={{ width: `${widthPct}%` }}
                  className="h-full bg-purple-500 border-r border-zinc-950/40 relative group"
                  title={`Segment ${i + 1}: ${(seg.duration_ms / 1000).toFixed(1)}s`}
                />
              );
            })
          ) : (
            <div className="w-full h-full bg-purple-600" />
          )}
        </div>
        <span className="font-mono text-zinc-400 text-[11px] shrink-0">
          Clean EDL: {((edl?.total_out_duration_ms || durationS * 1000) / 1000).toFixed(1)}s (
          {((edl?.removed_duration_ms || 0) / 1000).toFixed(1)}s cuts)
        </span>
      </div>

      {/* Modals & Dialogs */}
      <ConflictDialog />
      <RegenerateDialog isOpen={isRegenerateOpen} onClose={() => setIsRegenerateOpen(false)} />
    </div>
  );
}
