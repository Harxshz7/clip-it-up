"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scissors, Upload, BarChart3, LayoutDashboard, Sparkles } from "lucide-react";
import { useAppStore } from "@/lib/store";

export function Navbar() {
  const pathname = usePathname();
  const setUploadModalOpen = useAppStore((s) => s.setUploadModalOpen);

  return (
    <nav className="sticky top-0 z-40 border-b border-white/10 bg-[#0c0f17]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8 h-16">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-500 shadow-md shadow-purple-500/20 group-hover:scale-105 transition-transform">
              <Scissors className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-xl tracking-tight text-white flex items-center gap-1.5">
              clip<span className="text-purple-400">it</span>up
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-950/60 px-2 py-0.5 text-[10px] font-medium text-purple-300 border border-purple-800/50">
                <Sparkles className="w-2.5 h-2.5 text-purple-400" /> Phase 0
              </span>
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-1 text-sm font-medium">
            <Link
              href="/dashboard"
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg transition-colors ${
                pathname.startsWith("/dashboard") || pathname.startsWith("/videos")
                  ? "bg-white/10 text-white"
                  : "text-zinc-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setUploadModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 hover:shadow-purple-500/35 active:scale-95 transition-all"
          >
            <Upload className="h-4 w-4" />
            Upload Video
          </button>

          <div className="flex items-center gap-2 pl-3 border-l border-white/10">
            <div className="flex items-center gap-2 rounded-full bg-zinc-800/80 px-3 py-1.5 border border-white/5 text-xs text-zinc-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Dev User</span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
