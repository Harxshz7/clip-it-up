"use client";

import React from "react";
import { useEditorStore } from "@/lib/editorStore";
import { History, Sparkles, X, Check } from "lucide-react";

export const DraftRecoveryBanner: React.FC = () => {
  const { localDraftAvailable, restoreLocalDraft, discardLocalDraft } = useEditorStore();

  if (!localDraftAvailable) return null;

  return (
    <div className="bg-purple-950/70 border border-purple-600/50 rounded-xl p-3 flex items-center justify-between gap-4 text-xs shadow-lg animate-in fade-in">
      <div className="flex items-center gap-2.5">
        <History className="w-4 h-4 text-purple-400 shrink-0" />
        <div>
          <span className="font-bold text-white block">Unsaved Local Draft Found</span>
          <span className="text-[11px] text-purple-200">
            A newer draft was saved locally from a previous browser session.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={restoreLocalDraft}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition-colors"
        >
          <Check className="w-3.5 h-3.5" />
          <span>Restore Draft</span>
        </button>
        <button
          onClick={discardLocalDraft}
          className="px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium text-xs transition-colors"
        >
          Discard
        </button>
      </div>
    </div>
  );
};
