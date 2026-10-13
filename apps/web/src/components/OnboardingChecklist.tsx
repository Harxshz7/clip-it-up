"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { CheckCircle2, Circle, Sparkles, X, ArrowRight, Play, Scissors } from "lucide-react";
import { useAppStore } from "@/lib/store";

interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  href?: string;
  onClick?: () => void;
  completed: boolean;
}

export function OnboardingChecklist({ hasUploadedVideos }: { hasUploadedVideos: boolean }) {
  const [dismissed, setDismissed] = useState(false);
  const setUploadModalOpen = useAppStore((s) => s.setUploadModalOpen);

  useEffect(() => {
    const isDismissed = localStorage.getItem("ciu_onboarding_dismissed");
    if (isDismissed === "true") {
      setDismissed(true);
    }
  }, []);

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem("ciu_onboarding_dismissed", "true");
  };

  if (dismissed) return null;

  const items: ChecklistItem[] = [
    {
      id: "sample",
      title: "Explore Sample Project",
      description: "Preview AI-selected clips from our precomputed demo with zero upload.",
      href: "/videos/00000000-0000-0000-0000-000000000099/clips",
      completed: true,
    },
    {
      id: "upload",
      title: "Upload Your First Video",
      description: "Import a podcast episode, interview, or talk (up to 120 mins).",
      onClick: () => setUploadModalOpen(true),
      completed: hasUploadedVideos,
    },
    {
      id: "editor",
      title: "Polish in Studio Editor",
      description: "Refine your hook, eliminate filler words, and verify speaker reframe.",
      href: "/videos/00000000-0000-0000-0000-000000000099/clips",
      completed: false,
    },
    {
      id: "export",
      title: "Export Your First Viral Short",
      description: "Render high-definition 9:16 vertical video for TikTok or Instagram Reels.",
      href: "/videos/00000000-0000-0000-0000-000000000099/clips",
      completed: false,
    },
  ];

  const completedCount = items.filter((i) => i.completed).length;
  const progressPct = Math.round((completedCount / items.length) * 100);

  return (
    <div className="glass-panel-glow rounded-3xl p-5 sm:p-6 border border-purple-500/30 text-white relative shadow-xl">
      <button
        onClick={handleDismiss}
        className="absolute top-4 right-4 text-zinc-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
        title="Dismiss checklist"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-purple-300">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Creator Quickstart</span>
          </div>
          <h3 className="text-base font-bold text-white mt-0.5">
            Get up and running ({completedCount}/{items.length} steps)
          </h3>
        </div>

        <div className="w-full sm:w-48 space-y-1">
          <div className="flex justify-between text-[11px] text-zinc-400">
            <span>Progress</span>
            <span className="font-semibold text-purple-300">{progressPct}%</span>
          </div>
          <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500 rounded-full"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {items.map((item) => {
          const content = (
            <div
              className={`p-3.5 rounded-2xl border transition-all h-full flex flex-col justify-between ${
                item.completed
                  ? "bg-purple-950/20 border-purple-500/20 text-zinc-300"
                  : "bg-white/[0.02] border-white/5 hover:border-purple-500/30 hover:bg-white/[0.04]"
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  {item.completed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <Circle className="w-4 h-4 text-zinc-500 shrink-0" />
                  )}
                  <h4 className="text-xs font-bold text-white truncate">{item.title}</h4>
                </div>
                <p className="text-[11px] text-zinc-400 leading-snug line-clamp-2">
                  {item.description}
                </p>
              </div>

              <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] font-semibold text-purple-400">
                <span>{item.completed ? "Done" : "Start now"}</span>
                <ArrowRight className="w-3 h-3" />
              </div>
            </div>
          );

          if (item.href) {
            return (
              <Link key={item.id} href={item.href} className="block">
                {content}
              </Link>
            );
          }

          return (
            <button key={item.id} onClick={item.onClick} className="text-left w-full">
              {content}
            </button>
          );
        })}
      </div>
    </div>
  );
}
