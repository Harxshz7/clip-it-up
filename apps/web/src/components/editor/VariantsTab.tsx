"use client";

import React, { useEffect, useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { api } from "@/lib/api";
import {
  Sparkles,
  Layers,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  TrendingUp,
  Sliders,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  FileArchive,
  Eye,
  Check,
} from "lucide-react";
import { VariantSet, ClipVariant, VariantDimension } from "@clip-it-up/shared";

export const VariantsTab: React.FC = () => {
  const { doc, setDocDirect } = useEditorStore();
  const [variantSet, setVariantSet] = useState<VariantSet | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Generation options
  const [count, setCount] = useState<number>(4);
  const [dimHook, setDimHook] = useState(true);
  const [dimStyle, setDimStyle] = useState(true);
  const [dimCTA, setDimCTA] = useState(true);
  const [ctaGoal, setCtaGoal] = useState<string>("follow");

  // Selection for batch export
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [exportPreset, setExportPreset] = useState<string>("tiktok");

  // Expanded metrics logging accordion
  const [expandedMetricsId, setExpandedMetricsId] = useState<string | null>(null);
  const [metricsForm, setMetricsForm] = useState<{
    platform: string;
    url: string;
    views: number;
    likes: number;
    avg_watch_pct: number;
  }>({
    platform: "tiktok",
    url: "",
    views: 0,
    likes: 0,
    avg_watch_pct: 0,
  });

  const clipId = doc?.clip_id;

  const loadVariants = async () => {
    if (!clipId) return;
    try {
      setLoading(true);
      const data = await api.getClipVariants(clipId);
      setVariantSet(data);
      if (data?.variants) {
        setSelectedIds(data.variants.map((v) => v.id));
      }
    } catch {
      setVariantSet(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVariants();
  }, [clipId]);

  const handleGenerate = async () => {
    if (!clipId) return;
    try {
      setGenerating(true);
      setError(null);
      setSuccessMsg(null);

      const dimensions: VariantDimension[] = [];
      if (dimHook) dimensions.push("hook");
      if (dimStyle) dimensions.push("style");
      if (dimCTA) dimensions.push("cta");

      const res = await api.generateVariants(clipId, {
        count,
        dimensions,
        cta_goal: ctaGoal,
        include_baseline: true,
      });

      setVariantSet(res);
      setSelectedIds(res.variants.map((v) => v.id));
      setSuccessMsg(`Generated ${res.variants.length} optimized variants with baseline.`);
    } catch (err: any) {
      setError(err?.message || "Failed to generate auto-variants. Check plan limits.");
    } finally {
      setGenerating(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleBatchExport = async () => {
    if (!variantSet || selectedIds.length === 0) return;
    try {
      setExporting(true);
      setError(null);
      const res = await api.batchExportVariants(variantSet.id, {
        variant_ids: selectedIds,
        preset_key: exportPreset,
      });
      setSuccessMsg(res.message);
      await loadVariants();
    } catch (err: any) {
      setError(err?.message || "Batch export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleApplyVariant = (variant: ClipVariant) => {
    if (variant.edit_doc) {
      setDocDirect(variant.edit_doc);
      setSuccessMsg(`Applied '${variant.label}' to editor!`);
    }
  };

  const handleSaveMetrics = async (exportId?: string | null) => {
    if (!exportId) {
      setError("This variant must be exported before logging metrics.");
      return;
    }
    try {
      await api.updateExportMetrics(exportId, metricsForm);
      setSuccessMsg("Performance metrics saved successfully!");
      setExpandedMetricsId(null);
    } catch (err: any) {
      setError(err?.message || "Failed to save metrics");
    }
  };

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      {/* Header */}
      <div className="pb-3 border-b border-zinc-800">
        <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-purple-400" />
          Auto-Variants Combinator
        </h3>
        <p className="text-zinc-400 text-[11px] mt-0.5">
          Fork edit documents across hooks, caption styles, and high-converting CTAs.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-700/50 text-red-200 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-600/40 text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Generator Configuration Box */}
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
        <h4 className="font-semibold text-white flex items-center gap-1.5">
          <Sliders className="w-3.5 h-3.5 text-purple-400" />
          Generate Variants
        </h4>

        {/* Count Selector */}
        <div className="space-y-1">
          <div className="flex justify-between text-[11px] text-zinc-400">
            <span>Variants to Generate</span>
            <span className="font-bold text-white">{count} variants</span>
          </div>
          <div className="flex gap-2">
            {[2, 3, 4, 6].map((num) => (
              <button
                key={num}
                type="button"
                onClick={() => setCount(num)}
                className={`flex-1 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                  count === num
                    ? "bg-purple-600/30 border-purple-500 text-purple-200"
                    : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                {num}
              </button>
            ))}
          </div>
        </div>

        {/* Dimension Toggles */}
        <div className="space-y-1.5">
          <label className="text-zinc-400 text-[11px] block font-medium">Combinator Dimensions</label>
          <div className="grid grid-cols-3 gap-2">
            <label className="flex items-center gap-1.5 p-2 rounded-lg bg-zinc-950 border border-zinc-800 cursor-pointer">
              <input
                type="checkbox"
                checked={dimHook}
                onChange={(e) => setDimHook(e.target.checked)}
                className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
              />
              <span className="text-[11px]">Hooks</span>
            </label>
            <label className="flex items-center gap-1.5 p-2 rounded-lg bg-zinc-950 border border-zinc-800 cursor-pointer">
              <input
                type="checkbox"
                checked={dimStyle}
                onChange={(e) => setDimStyle(e.target.checked)}
                className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
              />
              <span className="text-[11px]">Styles</span>
            </label>
            <label className="flex items-center gap-1.5 p-2 rounded-lg bg-zinc-950 border border-zinc-800 cursor-pointer">
              <input
                type="checkbox"
                checked={dimCTA}
                onChange={(e) => setDimCTA(e.target.checked)}
                className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
              />
              <span className="text-[11px]">CTA</span>
            </label>
          </div>
        </div>

        {/* CTA Goal Selector */}
        <div className="space-y-1">
          <label className="text-zinc-400 text-[11px] block font-medium">Conversion CTA Goal</label>
          <select
            value={ctaGoal}
            onChange={(e) => setCtaGoal(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-white text-xs focus:outline-none focus:border-purple-500"
          >
            <option value="follow">Follow for More (Growth)</option>
            <option value="link_in_bio">Link in Bio (Traffic / Leads)</option>
            <option value="subscribe">Subscribe (Podcast / YouTube)</option>
            <option value="comment">Discussion / Comment (Viral Debate)</option>
          </select>
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={generating}
          className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-600/20 disabled:opacity-50 transition-all"
        >
          {generating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Generating Multi-Angle Variants...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Generate Auto-Variants</span>
            </>
          )}
        </button>
      </div>

      {/* Variant Cards Grid */}
      {variantSet?.variants && variantSet.variants.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-white">
              Generated Variants ({variantSet.variants.length})
            </h4>
            <span className="text-[10px] text-zinc-500">
              {selectedIds.length} of {variantSet.variants.length} selected
            </span>
          </div>

          <div className="space-y-3">
            {variantSet.variants.map((v, idx) => (
              <div
                key={v.id}
                className={`p-3.5 rounded-xl border transition-all ${
                  selectedIds.includes(v.id)
                    ? "bg-zinc-900 border-purple-500/50 shadow-md"
                    : "bg-zinc-950 border-zinc-800/80"
                }`}
              >
                {/* Header row */}
                <div className="flex items-center justify-between pb-2 border-b border-zinc-800/60">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(v.id)}
                      onChange={() => toggleSelect(v.id)}
                      className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="font-bold text-white text-xs">{v.label}</span>
                  </label>
                  {idx === 0 && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-300">
                      Baseline
                    </span>
                  )}
                </div>

                {/* Body info */}
                <div className="py-2.5 space-y-1.5 text-[11px]">
                  <div>
                    <span className="text-zinc-500">Hook: </span>
                    <span className="text-zinc-200 font-medium">&ldquo;{v.hook_text}&rdquo;</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="text-zinc-500">Style: </span>
                      <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-purple-300 font-mono text-[10px]">
                        {v.caption_style_key || "bold_pop"}
                      </span>
                    </div>
                    {v.cta_text && (
                      <div>
                        <span className="text-zinc-500">CTA: </span>
                        <span className="text-emerald-400 font-medium">{v.cta_text}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60 text-xs">
                  <button
                    type="button"
                    onClick={() => handleApplyVariant(v)}
                    className="text-purple-400 hover:text-purple-300 font-semibold text-[11px] flex items-center gap-1"
                  >
                    <span>Load in Editor</span>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setExpandedMetricsId(expandedMetricsId === v.id ? null : v.id)
                    }
                    className="text-zinc-400 hover:text-zinc-200 text-[11px] flex items-center gap-1"
                  >
                    <TrendingUp className="w-3 h-3 text-purple-400" />
                    <span>Log Performance</span>
                    {expandedMetricsId === v.id ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                </div>

                {/* Performance Metrics Logger Form */}
                {expandedMetricsId === v.id && (
                  <div className="mt-3 p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-2.5">
                    <h5 className="font-semibold text-white text-[11px] flex items-center gap-1">
                      <TrendingUp className="w-3 h-3 text-purple-400" />
                      Post Performance Logger
                    </h5>

                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <label className="text-zinc-400 text-[10px] block">Platform</label>
                        <select
                          value={metricsForm.platform}
                          onChange={(e) =>
                            setMetricsForm({ ...metricsForm, platform: e.target.value })
                          }
                          className="w-full px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-white text-xs"
                        >
                          <option value="tiktok">TikTok</option>
                          <option value="reels">Instagram Reels</option>
                          <option value="shorts">YouTube Shorts</option>
                          <option value="linkedin">LinkedIn</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-zinc-400 text-[10px] block">Published URL</label>
                        <input
                          type="text"
                          placeholder="https://..."
                          value={metricsForm.url}
                          onChange={(e) =>
                            setMetricsForm({ ...metricsForm, url: e.target.value })
                          }
                          className="w-full px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-white text-xs"
                        >
                        </input>
                      </div>

                      <div>
                        <label className="text-zinc-400 text-[10px] block">Views Count</label>
                        <input
                          type="number"
                          value={metricsForm.views}
                          onChange={(e) =>
                            setMetricsForm({ ...metricsForm, views: Number(e.target.value) })
                          }
                          className="w-full px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-white text-xs"
                        />
                      </div>

                      <div>
                        <label className="text-zinc-400 text-[10px] block">Avg Watch %</label>
                        <input
                          type="number"
                          step="0.1"
                          max="100"
                          value={metricsForm.avg_watch_pct}
                          onChange={(e) =>
                            setMetricsForm({
                              ...metricsForm,
                              avg_watch_pct: Number(e.target.value),
                            })
                          }
                          className="w-full px-2 py-1.5 rounded bg-zinc-900 border border-zinc-700 text-white text-xs"
                        />
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleSaveMetrics(v.export_id)}
                      className="w-full py-1.5 rounded bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors"
                    >
                      Save Results
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Batch Export & Zip Controls */}
          <div className="pt-3 border-t border-zinc-800 space-y-3">
            <div className="flex items-center gap-2">
              <select
                value={exportPreset}
                onChange={(e) => setExportPreset(e.target.value)}
                className="flex-1 px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-white text-xs"
              >
                <option value="tiktok">TikTok (9:16 vertical)</option>
                <option value="reels">Instagram Reels (9:16)</option>
                <option value="shorts">YouTube Shorts (9:16)</option>
              </select>

              <button
                type="button"
                onClick={handleBatchExport}
                disabled={exporting || selectedIds.length === 0}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-purple-600/20 disabled:opacity-50 transition-all"
              >
                {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                <span>Export Selected ({selectedIds.length})</span>
              </button>
            </div>

            <a
              href={api.getVariantSetZipDownloadUrl(variantSet.id)}
              download
              className="w-full py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/60 text-zinc-300 font-semibold text-xs flex items-center justify-center gap-2 transition-colors block text-center"
            >
              <FileArchive className="w-3.5 h-3.5 text-purple-400" />
              <span>Download Zip Archive + Manifest CSV</span>
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
