"use client";

import React, { useState } from "react";
import { useEditorStore } from "@/lib/editorStore";
import { Sparkles, Palette, Type, Check, RotateCcw } from "lucide-react";

const BUILT_IN_STYLES = [
  {
    key: "bold_pop",
    name: "Bold Pop",
    description: "High impact viral subtitle style with yellow active highlight and heavy black outline.",
    previewText: "VIRAL HOOK",
    primaryColor: "#FFFFFF",
    highlightColor: "#FACC15",
  },
  {
    key: "neon_pulse",
    name: "Neon Pulse",
    description: "Vibrant cyan & magenta neon glow ideal for podcasts and nightlife interviews.",
    previewText: "NEON GLOW",
    primaryColor: "#FFFFFF",
    highlightColor: "#06B6D4",
  },
  {
    key: "clean_minimal",
    name: "Clean Minimal",
    description: "Modern Apple-style elegant typography with subtle background blur pill.",
    previewText: "Clean Style",
    primaryColor: "#FFFFFF",
    highlightColor: "#10B981",
  },
];

export const CaptionsTab: React.FC = () => {
  const {
    doc,
    setCaptionStyle,
    setCaptionStyleOverrides,
    setCaptionEnabled,
    setBrandConfig,
  } = useEditorStore();

  const activeStyleKey = doc?.captions.style_key || "bold_pop";
  const isEnabled = doc?.captions.enabled !== false;
  const overrides = doc?.captions.style_overrides || {};
  const applyBrandStyle = doc?.brand?.apply_style !== false;

  return (
    <div className="p-4 space-y-6 text-xs text-zinc-300 overflow-y-auto max-h-[calc(100vh-220px)]">
      {/* Enable Toggle Header */}
      <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
        <div>
          <h3 className="font-semibold text-white text-sm">Subtitle Captions</h3>
          <p className="text-zinc-400 text-[11px]">Display dynamic animated subtitles on video</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => setCaptionEnabled(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
        </label>
      </div>

      {/* Brand Style Override Toggle */}
      <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <div>
            <span className="font-semibold text-white block text-xs">Apply Brand Kit Styling</span>
            <span className="text-[10px] text-zinc-400">
              Use brand kit font family and color palette
            </span>
          </div>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={applyBrandStyle}
            onChange={(e) => setBrandConfig({ apply_style: e.target.checked })}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
        </label>
      </div>

      {isEnabled && (
        <>
          {/* Style Packs */}
          <div className="space-y-3">
            <h4 className="font-semibold text-white flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              Style Packs
            </h4>

            <div className="grid grid-cols-1 gap-2.5">
              {BUILT_IN_STYLES.map((style) => {
                const isSelected = activeStyleKey === style.key;
                return (
                  <div
                    key={style.key}
                    onClick={() => setCaptionStyle(style.key)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-purple-950/40 border-purple-500 shadow-md shadow-purple-900/20"
                        : "bg-zinc-900/80 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-white text-sm flex items-center gap-1.5">
                        {style.name}
                        {isSelected && <Check className="w-3.5 h-3.5 text-purple-400" />}
                      </span>
                      <span
                        className="text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-wider"
                        style={{
                          backgroundColor: "#18181b",
                          color: style.highlightColor,
                          border: `1px solid ${style.highlightColor}40`,
                        }}
                      >
                        {style.previewText}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-normal">{style.description}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Style Customization Overrides */}
          <div className="space-y-4 pt-2 border-t border-zinc-800">
            <h4 className="font-semibold text-white flex items-center gap-1.5">
              <Palette className="w-3.5 h-3.5 text-purple-400" />
              Custom Overrides
            </h4>

            {/* Uppercase Toggle */}
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-zinc-200">Uppercase All Words</span>
              <input
                type="checkbox"
                checked={overrides.uppercase !== false}
                onChange={(e) => setCaptionStyleOverrides({ uppercase: e.target.checked })}
                className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
              />
            </div>

            {/* Highlight color picker */}
            <div className="space-y-1.5">
              <label className="text-zinc-400 text-[11px]">Active Highlight Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={overrides.highlight_color || "#FACC15"}
                  onChange={(e) => setCaptionStyleOverrides({ highlight_color: e.target.value })}
                  className="w-8 h-8 rounded border border-zinc-700 bg-transparent cursor-pointer"
                />
                <span className="font-mono text-xs text-zinc-300">
                  {overrides.highlight_color || "#FACC15"}
                </span>
              </div>
            </div>

            {/* Font size */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-400 text-[11px]">
                <span>Font Size Scale</span>
                <span>{overrides.font_size_pt || 32}pt</span>
              </div>
              <input
                type="range"
                min="20"
                max="48"
                value={overrides.font_size_pt || 32}
                onChange={(e) =>
                  setCaptionStyleOverrides({ font_size_pt: Number(e.target.value) })
                }
                className="w-full accent-purple-500"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
};
