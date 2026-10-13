"use client";

import { useState, useEffect } from "react";
import { Sparkles, Mic, Users, Video, Globe, ArrowRight, Check } from "lucide-react";

export function SignupSurveyModal() {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const answered = localStorage.getItem("ciu_survey_answered");
    if (!answered) {
      setOpen(true);
    }
  }, []);

  if (!open) return null;

  const options = [
    { id: "podcast", label: "Podcast / Vodcast", icon: Mic, desc: "Long multi-speaker conversations" },
    { id: "interview", label: "Interviews & Panels", icon: Users, desc: "Q&A, webinars, and discussions" },
    { id: "solo", label: "Solo / Talking Head", icon: Video, desc: "Educational tutorials, commentary, vlogs" },
    { id: "other", label: "Agency / Other", icon: Globe, desc: "Repurposing client video content" },
  ];

  const handleSubmit = async () => {
    if (!selected) return;
    try {
      setSaving(true);
      localStorage.setItem("ciu_survey_answered", selected);
      // If user is authenticated, we could also call api
    } finally {
      setSaving(false);
      setOpen(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md glass-panel-glow rounded-3xl p-6 sm:p-8 border border-purple-500/30 text-white space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 text-xs font-semibold border border-purple-500/30">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Welcome to clip-it-up</span>
          </div>
          <h2 className="text-xl font-bold text-white">What type of content do you create?</h2>
          <p className="text-xs text-zinc-400">
            This helps our AI calibrate narrative hooks and optimal aspect ratios.
          </p>
        </div>

        <div className="space-y-2.5">
          {options.map((opt) => {
            const Icon = opt.icon;
            const isSel = selected === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => setSelected(opt.id)}
                className={`w-full flex items-center justify-between p-3.5 rounded-2xl border text-left transition-all ${
                  isSel
                    ? "bg-purple-900/40 border-purple-500/60 shadow-md text-white"
                    : "bg-white/[0.02] border-white/10 hover:border-white/20 text-zinc-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-xl ${isSel ? "bg-purple-600 text-white" : "bg-white/5 text-zinc-400"}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">{opt.label}</h4>
                    <p className="text-[11px] text-zinc-400">{opt.desc}</p>
                  </div>
                </div>
                {isSel && <Check className="w-4 h-4 text-purple-400" />}
              </button>
            );
          })}
        </div>

        <button
          onClick={handleSubmit}
          disabled={!selected || saving}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white shadow-lg shadow-purple-500/25 active:scale-95 transition-all"
        >
          <span>Continue to Studio</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
