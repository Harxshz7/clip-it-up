"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  Upload,
  Check,
  AlertTriangle,
  Shield,
  Layers,
  ArrowRight,
  Eye,
  Trash2,
  CheckCircle2,
  Loader2,
  Lock,
  Type,
  Palette,
  Video,
  Sliders,
} from "lucide-react";
import { api } from "@/lib/api";
import { checkContrast } from "@/lib/contrast";
import { BrandKit, UserBillingMe } from "@clip-it-up/shared";

export default function BrandSettingsPage() {
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [selectedKit, setSelectedKit] = useState<BrandKit | null>(null);
  const [billingMe, setBillingMe] = useState<UserBillingMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Form edit state for currently selected kit
  const [kitName, setKitName] = useState("Default Brand");
  const [primaryColor, setPrimaryColor] = useState("#8B5CF6");
  const [secondaryColor, setSecondaryColor] = useState("#6366F1");
  const [textColor, setTextColor] = useState("#FFFFFF");
  const [highlightColor, setHighlightColor] = useState("#FACC15");
  const [bgColor, setBgColor] = useState("#0F172A");

  const [logoPosition, setLogoPosition] = useState<"top_left" | "top_right" | "bottom_left" | "bottom_right">("top_right");
  const [logoOpacity, setLogoOpacity] = useState(1.0);
  const [logoScale, setLogoScale] = useState(0.15);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);
  const [logoAssetId, setLogoAssetId] = useState<string | null>(null);

  const [fontLicenseAck, setFontLicenseAck] = useState(false);
  const [fontFileName, setFontFileName] = useState<string | null>(null);
  const [fontWarning, setFontWarning] = useState<string | null>(null);

  const [introFileName, setIntroFileName] = useState<string | null>(null);
  const [outroFileName, setOutroFileName] = useState<string | null>(null);
  const [introAssetId, setIntroAssetId] = useState<string | null>(null);
  const [outroAssetId, setOutroAssetId] = useState<string | null>(null);

  const isFreePlan = billingMe?.plan?.key === "free" || !billingMe?.plan?.features?.brand_kit;

  const loadData = async () => {
    try {
      setLoading(true);
      const [kitsData, meData] = await Promise.all([
        api.listBrandKits().catch(() => []),
        api.getBillingMe().catch(() => null),
      ]);
      setKits(kitsData);
      setBillingMe(meData);

      if (kitsData.length > 0) {
        const defaultKit = kitsData.find((k) => k.is_default) || kitsData[0];
        selectKit(defaultKit);
      }
    } catch (err: any) {
      console.error("Failed to load brand data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const selectKit = (kit: BrandKit) => {
    setSelectedKit(kit);
    setKitName(kit.name);
    setPrimaryColor(kit.colors?.primary || "#8B5CF6");
    setSecondaryColor(kit.colors?.secondary || "#6366F1");
    setTextColor(kit.colors?.text || "#FFFFFF");
    setHighlightColor(kit.colors?.highlight || "#FACC15");
    setBgColor(kit.colors?.background || "#0F172A");

    setLogoPosition(kit.logo_position || "top_right");
    setLogoOpacity(kit.logo_opacity ?? 1.0);
    setLogoScale(kit.logo_scale ?? 0.15);
    setLogoAssetId(kit.logo_asset_id || null);
    setLogoPreviewUrl(kit.logo_asset?.download_url || null);

    setIntroAssetId(kit.intro_asset_id || null);
    setOutroAssetId(kit.outro_asset_id || null);
    setIntroFileName(kit.intro_asset?.filename || null);
    setOutroFileName(kit.outro_asset?.filename || null);
  };

  // WCAG contrast calculation
  const textContrast = checkContrast(textColor, bgColor);
  const highlightContrast = checkContrast(highlightColor, bgColor);

  // Logo file upload handler
  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setMessage(null);
      const res = await api.getBrandAssetUploadUrl({
        filename: file.name,
        content_type: file.type || "image/png",
        size_bytes: file.size,
        kind: "logo",
      });

      // Direct upload
      await fetch(res.upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type || "image/png" },
        body: file,
      });

      const completed = await api.completeBrandAsset(res.asset_id, {});
      setLogoAssetId(completed.id);
      setLogoPreviewUrl(URL.createObjectURL(file));
      setMessage({ text: "Logo uploaded successfully!", type: "success" });
    } catch (err: any) {
      setMessage({ text: err?.message || "Failed to upload logo", type: "error" });
    }
  };

  // Font upload handler
  const handleFontUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!fontLicenseAck) {
      setMessage({ text: "You must confirm you hold commercial license rights for this font.", type: "error" });
      return;
    }

    try {
      setMessage(null);
      const res = await api.getBrandAssetUploadUrl({
        filename: file.name,
        content_type: "font/ttf",
        size_bytes: file.size,
        kind: "font",
      });

      await fetch(res.upload_url, {
        method: "PUT",
        body: file,
      });

      const completed = await api.completeBrandAsset(res.asset_id, { license_acknowledged: true });
      setFontFileName(file.name);
      if (completed.metadata_json?.warning) {
        setFontWarning(completed.metadata_json.warning);
      } else {
        setFontWarning(null);
      }
      setMessage({ text: `Custom font '${file.name}' verified and uploaded!`, type: "success" });
    } catch (err: any) {
      setMessage({ text: err?.message || "Font validation failed", type: "error" });
    }
  };

  // Intro/Outro upload handler
  const handleVideoUpload = async (kind: "intro" | "outro", e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setMessage(null);
      const res = await api.getBrandAssetUploadUrl({
        filename: file.name,
        content_type: "video/mp4",
        size_bytes: file.size,
        kind,
      });

      await fetch(res.upload_url, {
        method: "PUT",
        headers: { "Content-Type": "video/mp4" },
        body: file,
      });

      const completed = await api.completeBrandAsset(res.asset_id, {});
      if (kind === "intro") {
        setIntroAssetId(completed.id);
        setIntroFileName(file.name);
      } else {
        setOutroAssetId(completed.id);
        setOutroFileName(file.name);
      }
      setMessage({ text: `${kind === "intro" ? "Intro" : "Outro"} video uploaded and validated!`, type: "success" });
    } catch (err: any) {
      setMessage({ text: err?.message || `Failed to upload ${kind}`, type: "error" });
    }
  };

  // Save / Update kit
  const handleSaveKit = async () => {
    try {
      setSaving(true);
      setMessage(null);

      const payload = {
        name: kitName,
        colors: {
          primary: primaryColor,
          secondary: secondaryColor,
          text: textColor,
          highlight: highlightColor,
          background: bgColor,
        },
        logo_asset_id: logoAssetId,
        logo_position: logoPosition,
        logo_opacity: logoOpacity,
        logo_scale: logoScale,
        intro_asset_id: introAssetId,
        outro_asset_id: outroAssetId,
      };

      if (selectedKit) {
        await api.updateBrandKit(selectedKit.id, payload);
        setMessage({ text: "Brand kit updated successfully!", type: "success" });
      } else {
        const created = await api.createBrandKit(payload);
        setMessage({ text: "New brand kit created!", type: "success" });
        selectKit(created);
      }
      await loadData();
    } catch (err: any) {
      setMessage({ text: err?.message || "Failed to save brand kit", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  // Set default kit
  const handleSetDefault = async (kitId: string) => {
    try {
      await api.setDefaultBrandKit(kitId);
      setMessage({ text: "Default brand kit updated!", type: "success" });
      await loadData();
    } catch (err: any) {
      setMessage({ text: err?.message || "Failed to set default kit", type: "error" });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-zinc-800">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-white flex items-center gap-2.5">
            <Sparkles className="w-7 h-7 text-purple-400" />
            Brand Kit &amp; Identity
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            Apply automated watermark-free branding, custom fonts, safe-zone logos, and intro/outro clips.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/settings/billing"
            className="px-4 py-2 rounded-xl bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/60 text-xs font-semibold text-zinc-300 transition-colors"
          >
            Manage Subscription
          </Link>
          <button
            onClick={handleSaveKit}
            disabled={saving || isFreePlan}
            className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-purple-600/20 disabled:opacity-50 transition-all"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            Save Brand Kit
          </button>
        </div>
      </div>

      {/* Free Plan Lock Banner */}
      {isFreePlan && (
        <div className="p-6 rounded-2xl bg-gradient-to-r from-purple-950/60 via-zinc-900 to-zinc-900 border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xl">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-400 shrink-0">
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Brand Kit is locked on the Free tier</h2>
              <p className="text-zinc-400 text-xs mt-0.5">
                Upgrade to Creator or Pro Studio to upload custom transparent logos, branded typography, custom intro/outros, and render 100% watermark-free clips.
              </p>
            </div>
          </div>
          <Link
            href="/settings/billing"
            className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shrink-0 flex items-center justify-center gap-2 shadow-lg shadow-purple-600/30 transition-all"
          >
            <span>Upgrade to Creator</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      )}

      {message && (
        <div
          className={`p-4 rounded-xl border flex items-center gap-2.5 text-xs ${
            message.type === "success"
              ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-200"
              : "bg-red-950/40 border-red-500/40 text-red-200"
          }`}
        >
          {message.type === "success" ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-red-400" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Main Grid: Left Controls & Right Interactive 9:16 Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Form: Kit Settings */}
        <div className="lg:col-span-7 space-y-6">
          {/* Kit Details Card */}
          <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-white text-sm flex items-center gap-2">
                <Sliders className="w-4 h-4 text-purple-400" />
                Brand Kit Profile
              </h2>
              {selectedKit?.is_default && (
                <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-bold text-[10px] border border-purple-500/30">
                  Default Brand
                </span>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-zinc-400 text-xs">Kit Name</label>
              <input
                type="text"
                value={kitName}
                onChange={(e) => setKitName(e.target.value)}
                placeholder="e.g. Acme Podcasting Identity"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-white text-xs focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Logo Upload & Positioning Card */}
          <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h2 className="font-bold text-white text-sm flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              Logo Overlay (Watermark Replacement)
            </h2>

            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <label className="px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-semibold text-xs cursor-pointer flex items-center gap-2 border border-zinc-700 transition-colors">
                  <Upload className="w-4 h-4 text-purple-400" />
                  <span>Upload Logo (PNG, WebP, SVG)</span>
                  <input
                    type="file"
                    accept="image/png,image/webp,image/svg+xml"
                    onChange={handleLogoUpload}
                    disabled={isFreePlan}
                    className="hidden"
                  />
                </label>
                {logoPreviewUrl && (
                  <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Logo ready
                  </span>
                )}
              </div>

              {/* Placement Corners */}
              <div className="space-y-1.5 pt-2">
                <label className="text-zinc-400 text-xs font-semibold">Position Corner</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {(["top_left", "top_right", "bottom_left", "bottom_right"] as const).map((pos) => (
                    <button
                      key={pos}
                      type="button"
                      onClick={() => setLogoPosition(pos)}
                      className={`py-2 px-3 rounded-xl border text-xs capitalize transition-all ${
                        logoPosition === pos
                          ? "bg-purple-600/30 border-purple-500 text-purple-200 font-bold"
                          : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:bg-zinc-800"
                      }`}
                    >
                      {pos.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Scale & Opacity Sliders */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Scale</span>
                    <span className="font-mono text-zinc-200">{Math.round(logoScale * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="0.35"
                    step="0.01"
                    value={logoScale}
                    onChange={(e) => setLogoScale(parseFloat(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Opacity</span>
                    <span className="font-mono text-zinc-200">{Math.round(logoOpacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={logoOpacity}
                    onChange={(e) => setLogoOpacity(parseFloat(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Color Palette with WCAG Contrast Check */}
          <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-white text-sm flex items-center gap-2">
                <Palette className="w-4 h-4 text-purple-400" />
                Color Palette &amp; Contrast Validation
              </h2>
              <span className="text-[10px] text-zinc-500">WCAG 2.1 Compliant</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {[
                { label: "Primary", val: primaryColor, set: setPrimaryColor },
                { label: "Secondary", val: secondaryColor, set: setSecondaryColor },
                { label: "Highlight", val: highlightColor, set: setHighlightColor },
                { label: "Text", val: textColor, set: setTextColor },
                { label: "Background", val: bgColor, set: setBgColor },
              ].map((c) => (
                <div key={c.label} className="space-y-1.5 p-2 rounded-xl bg-zinc-950 border border-zinc-800">
                  <label className="text-[11px] text-zinc-400 block font-medium">{c.label}</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={c.val}
                      onChange={(e) => c.set(e.target.value)}
                      className="w-7 h-7 rounded border border-zinc-700 bg-transparent cursor-pointer"
                    />
                    <span className="font-mono text-[10px] text-zinc-300">{c.val}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Contrast check badges */}
            <div className="p-3.5 rounded-xl bg-zinc-950/70 border border-zinc-800 flex flex-wrap items-center gap-4 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-zinc-400 text-[11px]">Text / Background:</span>
                <span className={`font-mono font-bold ${textContrast.passesAA ? "text-emerald-400" : "text-amber-400"}`}>
                  {textContrast.ratioFormatted}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${textContrast.passesAA ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-amber-500/20 text-amber-300 border border-amber-500/30"}`}>
                  {textContrast.passesAA ? "Passes AA" : "Low Contrast"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-zinc-400 text-[11px]">Highlight / Background:</span>
                <span className={`font-mono font-bold ${highlightContrast.passesAA ? "text-emerald-400" : "text-amber-400"}`}>
                  {highlightContrast.ratioFormatted}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${highlightContrast.passesAA ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-amber-500/20 text-amber-300 border border-amber-500/30"}`}>
                  {highlightContrast.passesAA ? "Passes AA" : "Low Contrast"}
                </span>
              </div>
            </div>
          </div>

          {/* Typography & Font Upload Card */}
          <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h2 className="font-bold text-white text-sm flex items-center gap-2">
              <Type className="w-4 h-4 text-purple-400" />
              Custom Typography (TTF, OTF, WOFF2)
            </h2>

            <div className="space-y-3">
              <label className="flex items-start gap-2.5 text-xs text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={fontLicenseAck}
                  onChange={(e) => setFontLicenseAck(e.target.checked)}
                  className="mt-0.5 rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
                />
                <span>
                  I acknowledge and confirm that I own or hold valid commercial license rights to use this font in video renders.
                </span>
              </label>

              <div className="flex items-center gap-4">
                <label className={`px-4 py-2.5 rounded-xl font-semibold text-xs flex items-center gap-2 border transition-colors ${fontLicenseAck ? "bg-zinc-800 hover:bg-zinc-700 text-white cursor-pointer border-zinc-700" : "bg-zinc-900 text-zinc-500 cursor-not-allowed border-zinc-800"}`}>
                  <Upload className="w-4 h-4 text-purple-400" />
                  <span>Choose Font File</span>
                  <input
                    type="file"
                    accept=".ttf,.otf,.woff2"
                    onChange={handleFontUpload}
                    disabled={!fontLicenseAck || isFreePlan}
                    className="hidden"
                  />
                </label>
                {fontFileName && (
                  <span className="text-[11px] text-zinc-300 font-mono">
                    Active: {fontFileName}
                  </span>
                )}
              </div>

              {fontWarning && (
                <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-600/40 text-amber-300 text-[11px] flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>{fontWarning}</span>
                </div>
              )}
            </div>
          </div>

          {/* Intro / Outro Video Clips Card */}
          <div className="p-5 rounded-2xl bg-zinc-900 border border-zinc-800 space-y-4">
            <h2 className="font-bold text-white text-sm flex items-center gap-2">
              <Video className="w-4 h-4 text-purple-400" />
              Video Intro &amp; Outro Bumpers
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Intro */}
              <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2.5">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-white text-xs">Intro Bumper (Max 10s)</span>
                  {introFileName && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                </div>
                <label className="w-full py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium cursor-pointer flex items-center justify-center gap-1.5 transition-colors">
                  <Upload className="w-3.5 h-3.5 text-purple-400" />
                  <span>{introFileName ? "Replace Intro" : "Upload Intro MP4"}</span>
                  <input
                    type="file"
                    accept="video/mp4"
                    onChange={(e) => handleVideoUpload("intro", e)}
                    disabled={isFreePlan}
                    className="hidden"
                  />
                </label>
                {introFileName && <p className="text-[10px] text-zinc-400 truncate">{introFileName}</p>}
              </div>

              {/* Outro */}
              <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2.5">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-white text-xs">Outro Bumper (Max 10s)</span>
                  {outroFileName && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                </div>
                <label className="w-full py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium cursor-pointer flex items-center justify-center gap-1.5 transition-colors">
                  <Upload className="w-3.5 h-3.5 text-purple-400" />
                  <span>{outroFileName ? "Replace Outro" : "Upload Outro MP4"}</span>
                  <input
                    type="file"
                    accept="video/mp4"
                    onChange={(e) => handleVideoUpload("outro", e)}
                    disabled={isFreePlan}
                    className="hidden"
                  />
                </label>
                {outroFileName && <p className="text-[10px] text-zinc-400 truncate">{outroFileName}</p>}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live 9:16 Placement Preview Frame */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="sticky top-6 w-full max-w-[340px] space-y-3">
            <div className="flex items-center justify-between text-xs text-zinc-400 px-1">
              <span className="font-semibold text-white flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-purple-400" />
                Live 9:16 Safe-Zone Preview
              </span>
              <span>1080 &times; 1920</span>
            </div>

            {/* Vertical Video Phone Frame */}
            <div className="relative aspect-[9/16] w-full rounded-3xl bg-zinc-900 border-4 border-zinc-800 overflow-hidden shadow-2xl flex flex-col justify-between">
              {/* Background gradient simulation */}
              <div
                className="absolute inset-0 opacity-80"
                style={{
                  background: `radial-gradient(circle at 50% 30%, ${secondaryColor}33, ${bgColor} 90%)`,
                }}
              />

              {/* Safe zone overlay guide */}
              <div className="absolute inset-x-4 top-14 bottom-24 border border-dashed border-zinc-700/60 rounded-xl pointer-events-none flex flex-col justify-between p-2">
                <span className="text-[9px] text-zinc-500 uppercase font-mono tracking-wider">TikTok / Reels Safe Margins</span>
                <span className="text-[9px] text-zinc-500 uppercase font-mono tracking-wider self-end">Subtitles Zone</span>
              </div>

              {/* Top Header Mock */}
              <div className="relative z-10 p-4 flex justify-between items-center text-[10px] text-zinc-400">
                <span className="font-bold text-white tracking-wide">CLIP PREVIEW</span>
                <span className="bg-zinc-800/80 px-2 py-0.5 rounded-full text-zinc-300">00:15</span>
              </div>

              {/* Dynamic Logo Placement */}
              <div
                className={`absolute z-20 transition-all duration-200 pointer-events-none ${
                  logoPosition === "top_left"
                    ? "top-14 left-4"
                    : logoPosition === "top_right"
                    ? "top-14 right-4"
                    : logoPosition === "bottom_left"
                    ? "bottom-24 left-4"
                    : "bottom-24 right-4"
                }`}
                style={{ opacity: logoOpacity }}
              >
                {logoPreviewUrl ? (
                  <img
                    src={logoPreviewUrl}
                    alt="Brand Logo"
                    className="object-contain"
                    style={{ width: `${Math.round(logoScale * 300)}px`, maxHeight: "60px" }}
                  />
                ) : (
                  <div
                    className="px-2.5 py-1 rounded bg-white/20 backdrop-blur-sm border border-white/40 text-white font-black text-[11px] tracking-wider shadow"
                    style={{ transform: `scale(${logoScale / 0.15})`, transformOrigin: logoPosition.includes("right") ? "top right" : "top left" }}
                  >
                    BRAND LOGO
                  </div>
                )}
              </div>

              {/* Sample Subtitles Preview with Brand Colors */}
              <div className="relative z-10 px-6 pb-20 text-center space-y-1">
                <div
                  className="inline-block px-3 py-1.5 rounded-lg text-sm font-black tracking-wide shadow-lg"
                  style={{
                    backgroundColor: bgColor,
                    color: textColor,
                    border: `1px solid ${primaryColor}`,
                  }}
                >
                  <span>THIS IS HOW YOU </span>
                  <span style={{ color: highlightColor }}>DOMINATE</span>
                </div>
                <p className="text-[10px] text-zinc-400 font-medium">Automatic Brand Color Typography</p>
              </div>
            </div>

            <p className="text-[11px] text-zinc-500 text-center">
              Safe zones ensure your logo and subtitles are never cropped or hidden by mobile platform navigation bars.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
