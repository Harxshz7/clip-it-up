"use client";

import React from "react";
import { useEditorStore } from "@/lib/editorStore";
import { AlertTriangle, RefreshCw, UploadCloud, X } from "lucide-react";

export const ConflictDialog: React.FC = () => {
  const {
    saveStatus,
    conflictServerDoc,
    resolveConflictKeepMine,
    resolveConflictUseServer,
  } = useEditorStore();

  if (saveStatus !== "conflict") return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
        <div className="flex items-center gap-3 text-amber-400">
          <div className="p-2.5 rounded-full bg-amber-950/60 border border-amber-800/60">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-bold text-white text-base">Version Conflict</h3>
            <p className="text-zinc-400 text-xs">
              A newer version (v{conflictServerDoc?.version || "?"}) exists on the server.
            </p>
          </div>
        </div>

        <p className="text-xs text-zinc-300 leading-relaxed">
          Another tab or session saved changes to this clip. Choose whether to load the latest server version or overwrite it with your current edits.
        </p>

        <div className="flex flex-col gap-2 pt-2">
          <button
            onClick={resolveConflictUseServer}
            className="w-full py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Load Server Version (Recommended)</span>
          </button>

          <button
            onClick={resolveConflictKeepMine}
            className="w-full py-2.5 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold text-xs flex items-center justify-center gap-2 transition-colors"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Overwrite Server With My Edits</span>
          </button>
        </div>
      </div>
    </div>
  );
};
