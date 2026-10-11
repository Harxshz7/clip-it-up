"use client";

import React, { useEffect, useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { api } from "@/lib/api";
import { ExportPreset, ExportRecord, UserPlanMe } from "@clip-it-up/shared";
import {
  Download,
  Share2,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Loader2,
  Clock,
  Layers,
  ExternalLink,
} from "lucide-react";

export const ExportTab: React.FC = () => {
  const { doc } = useEditorStore();
  const [presets, setPresets] = useState<ExportPreset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>("tiktok");
  const [userPlan, setUserPlan] = useState<UserPlanMe | null>(null);
  const [exports, setExports] = useState<ExportRecord[]>([]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const startMs = doc?.range.start_ms || 0;
  const endMs = doc?.range.end_ms || 10000;
  const durationS = Math.round((endMs - startMs) / 1000);

  // Load presets, user plan, and clip export history
  useEffect(() => {
    async function loadData() {
      if (!doc?.clip_id) return;
      try {
        const [presetsData, planData, exportsData] = await Promise.all([
          api.listExportPresets().catch(() => []),
          api.getMyPlan().catch(() => null),
          api.listClipExports(doc.clip_id).catch(() => []),
        ]);
        setPresets(presetsData);
        setUserPlan(planData);
        setExports(exportsData);
      } catch (err) {
        console.error("Failed to load export tab data", err);
      }
    }
    loadData();
  }, [doc?.clip_id]);

  const handleExport = async (allPresets = false) => {
    if (!doc?.clip_id) return;
    try {
      setIsExporting(true);
      setExportError(null);

      const presetsToExport = allPresets
        ? presets.map((p) => p.key)
        : [selectedPreset];

      const res = await api.createClipExport(doc.clip_id, {
        presets: presetsToExport,
        doc_snapshot: doc,
        force: true,
      });

      // Update exports list
      setExports((prev) => [...res, ...prev]);
    } catch (err: any) {
      setExportError(err?.message || "Failed to trigger render export");
    } finally {
      setIsExporting(false);
    }
  };

  const activePresetConfig = presets.find((p) => p.key === selectedPreset);

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Download className="w-4 h-4 text-purple-400" />
          Render &amp; Export
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          Generate production-ready 1080x1920 MP4 vertical clips
        </p>
      </div>

      {exportError && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-700/50 text-red-200 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {/* Preset Selector */}
      <div className="space-y-3">
        <h4 className="font-semibold text-white">Target Platform Preset</h4>
        <div className="grid grid-cols-2 gap-2">
          {presets.map((p) => {
            const isSelected = selectedPreset === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => setSelectedPreset(p.key)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "bg-purple-950/50 border-purple-500 text-white shadow-md"
                    : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 text-zinc-400"
                }`}
              >
                <span className="font-bold text-sm block text-white">{p.name}</span>
                <span className="text-[10px] text-zinc-400 block font-mono">
                  {p.width}x{p.height} &bull; max {p.max_duration_s}s
                </span>
              </button>
            );
          })}
        </div>

        {/* Duration warning */}
        {activePresetConfig && durationS > activePresetConfig.max_duration_s && (
          <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/50 text-amber-200 flex items-center gap-2 text-[11px]">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              Clip is {durationS}s. {activePresetConfig.name} recommended max is{" "}
              {activePresetConfig.max_duration_s}s.
            </span>
          </div>
        )}
      </div>

      {/* Plan & Watermark indicator */}
      {userPlan && (
        <div className="p-3.5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-white flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              Plan: {userPlan.plan.name}
            </span>
            <span className="font-mono text-zinc-400 text-[11px]">
              {userPlan.monthly_exports_used} / {userPlan.monthly_exports_limit} exports used
            </span>
          </div>

          {userPlan.watermark_required && (
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-zinc-800">
              <span className="text-zinc-400">clip-it-up corner watermark applied</span>
              <a
                href="/pricing"
                className="text-purple-400 hover:text-purple-300 font-semibold underline"
              >
                Upgrade to Pro
              </a>
            </div>
          )}
        </div>
      )}

      {/* Export Action Buttons */}
      <div className="space-y-2 pt-2">
        <button
          type="button"
          onClick={() => handleExport(false)}
          disabled={isExporting}
          className="w-full py-3 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-purple-900/30 transition-all disabled:opacity-50"
        >
          {isExporting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Submitting Render Job...</span>
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              <span>Export {activePresetConfig?.name || "Clip"}</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={() => handleExport(true)}
          disabled={isExporting}
          className="w-full py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold text-xs flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Export All Presets Batch</span>
        </button>
      </div>

      {/* Export History List */}
      <div className="space-y-3 pt-3 border-t border-zinc-800">
        <h4 className="font-semibold text-white">Clip Export History ({exports.length})</h4>
        {exports.length === 0 ? (
          <p className="text-zinc-500 text-center py-4 text-xs">No exports yet for this clip.</p>
        ) : (
          <div className="space-y-2">
            {exports.map((exp) => (
              <div
                key={exp.id}
                className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between"
              >
                <div>
                  <span className="font-bold text-white uppercase text-[11px] block">
                    {exp.preset_key}
                  </span>
                  <span className="text-[10px] text-zinc-400 capitalize">
                    Status: <strong className={exp.status === "succeeded" ? "text-emerald-400" : "text-amber-400"}>{exp.status}</strong>
                  </span>
                </div>

                {exp.download_url && (
                  <a
                    href={exp.download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    <span>Download</span>
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
