"use client";

import React, { useState, useEffect } from "react";
import { ExportRecord } from "@clip-it-up/shared";
import { api } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/utils";
import {
  Download,
  Film,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  Layers,
  Sparkles,
} from "lucide-react";

interface ExportsListProps {
  videoId: string;
}

export function ExportsList({ videoId }: ExportsListProps) {
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchExports = async () => {
    try {
      setLoading(true);
      // Fetch clips for video
      const clipsRes = await api.getVideoClips(videoId);
      const allExports: ExportRecord[] = [];

      for (const moment of clipsRes.moments) {
        for (const clip of moment.clips) {
          const clipExp = await api.listClipExports(clip.id).catch(() => []);
          allExports.push(...clipExp);
        }
      }

      setExports(allExports);
    } catch (e) {
      console.error("Failed to load exports:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExports();
  }, [videoId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-purple-500 mr-2" />
        <span className="text-sm">Loading studio exports...</span>
      </div>
    );
  }

  if (exports.length === 0) {
    return (
      <div className="glass-panel p-8 rounded-2xl border border-white/5 text-center text-slate-400">
        <Film className="w-8 h-8 mx-auto mb-2 text-slate-500 opacity-60" />
        <p className="text-sm font-semibold text-slate-300 mb-1">No rendered exports yet</p>
        <p className="text-xs text-slate-500">
          Open any AI Clip and click &quot;Export&quot; to render platform-ready 1080x1920 vertical videos.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Layers className="w-4 h-4 text-purple-400" />
          Rendered Video Exports ({exports.length})
        </h3>
        <button
          onClick={fetchExports}
          className="text-xs text-purple-400 hover:text-purple-300 font-medium"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {exports.map((exp) => {
          const isSuccess = exp.status === "succeeded";
          const isFailed = exp.status === "failed";
          const isRendering = exp.status === "rendering" || exp.status === "queued";

          return (
            <div
              key={exp.id}
              className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-white uppercase tracking-wider bg-purple-950/80 border border-purple-800/60 px-2 py-0.5 rounded font-mono">
                    {exp.preset_key} (9:16)
                  </span>

                  {isSuccess ? (
                    <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Ready
                    </span>
                  ) : isRendering ? (
                    <span className="inline-flex items-center gap-1 text-[11px] text-indigo-400 font-medium">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Rendering
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] text-red-400 font-medium">
                      <AlertTriangle className="w-3.5 h-3.5" /> Failed
                    </span>
                  )}
                </div>

                <div className="text-xs text-slate-400 space-y-1">
                  <div className="flex items-center gap-2 text-[11px]">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <span>Duration: {exp.duration_ms ? formatDuration(exp.duration_ms / 1000.0) : "--"}</span>
                    {exp.size_bytes ? <span>• {formatBytes(exp.size_bytes)}</span> : null}
                    {exp.render_ms ? <span>• Render: {(exp.render_ms / 1000.0).toFixed(1)}s</span> : null}
                  </div>
                  {exp.params_snapshot?.style_key && (
                    <div className="text-[11px] text-slate-500">
                      Style: <span className="text-slate-300 font-medium">{exp.params_snapshot.style_key}</span>
                      {exp.params_snapshot.watermark ? " • Watermarked" : ""}
                    </div>
                  )}
                  {exp.error && <p className="text-[11px] text-red-400 mt-1">{exp.error}</p>}
                </div>
              </div>

              {isSuccess && exp.download_url && (
                <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(exp.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <a
                    href={exp.download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-all shadow-sm"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download MP4
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
