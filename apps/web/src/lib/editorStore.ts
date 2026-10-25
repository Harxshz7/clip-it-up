import { create } from "zustand";
import {
  ClipEditDoc,
  ClipEditRemoval,
  ClipEditCleanupOptions,
  ClipEditRecord,
  ClipEditBrand,
  EditDecisionList,
} from "@clip-it-up/shared";
import { api, ApiError } from "./api";
import { instrumentation } from "./instrumentation";

export type SaveStatus = "idle" | "saving" | "saved" | "error" | "conflict";
export type EditorTab = "transcript" | "captions" | "framing" | "cleanup" | "hook" | "variants" | "export";

export interface LocalDraft {
  clip_id: string;
  doc: ClipEditDoc;
  timestamp: number;
}

interface EditorState {
  // Document state
  doc: ClipEditDoc | null;
  serverVersion: number;
  initialDoc: ClipEditDoc | null;
  edl: EditDecisionList | null;

  // History & Undo/Redo
  history: ClipEditDoc[];
  future: ClipEditDoc[];

  // Save & Sync
  isDirty: boolean;
  saveStatus: SaveStatus;
  saveError: string | null;
  conflictServerDoc: ClipEditDoc | null;
  lastSavedAt: number | null;

  // Draft recovery
  localDraftAvailable: LocalDraft | null;

  // Playback & UI
  currentTimeMs: number;
  isPlaying: boolean;
  playbackRate: number;
  loopRange: boolean;
  showSafeZone: boolean;
  activeTab: EditorTab;

  // Actions
  init: (record: ClipEditRecord) => void;
  setDocDirect: (doc: ClipEditDoc) => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // Document Edits
  setRange: (range: { start_ms: number; end_ms: number }) => void;
  addManualRemoval: (removal: { start_ms: number; end_ms: number; text?: string | null }) => void;
  toggleRemoval: (id: string) => void;
  removeRemoval: (id: string) => void;
  setCleanupOptions: (options: Partial<ClipEditCleanupOptions>) => void;

  updateWordText: (wordIdx: number, text: string) => void;
  toggleWordEmphasis: (wordIdx: number) => void;
  deleteWordRange: (start_ms: number, end_ms: number, text: string) => void;

  setCaptionStyle: (styleKey: string) => void;
  setCaptionStyleOverrides: (overrides: Record<string, any>) => void;
  setCaptionEnabled: (enabled: boolean) => void;

  setReframeKeyframes: (keyframes: any[]) => void;
  setReframeModeOverride: (segmentKey: string, mode: string) => void;

  setHook: (hook: { text: string; source: "auto" | "alt" | "manual"; start_ms: number }) => void;
  setPresetKey: (presetKey: string) => void;
  setBrandConfig: (brand: Partial<ClipEditBrand>) => void;

  // Playback actions
  setCurrentTimeMs: (ms: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setPlaybackRate: (rate: number) => void;
  setLoopRange: (loop: boolean) => void;
  setShowSafeZone: (show: boolean) => void;
  setActiveTab: (tab: EditorTab) => void;

  // Persistence
  save: (isCheckpoint?: boolean, label?: string) => Promise<boolean>;
  triggerAutosave: () => void;
  resolveConflictKeepMine: () => Promise<void>;
  resolveConflictUseServer: () => void;
  restoreLocalDraft: () => void;
  discardLocalDraft: () => void;
  resetToAuto: () => Promise<void>;
}

const HISTORY_LIMIT = 200;
let autosaveTimeout: NodeJS.Timeout | null = null;

function saveDraftToStorage(clipId: string, doc: ClipEditDoc) {
  if (typeof window === "undefined") return;
  try {
    const draft: LocalDraft = {
      clip_id: clipId,
      doc,
      timestamp: Date.now(),
    };
    localStorage.setItem(`clip_draft_${clipId}`, JSON.stringify(draft));
  } catch {}
}

function loadDraftFromStorage(clipId: string): LocalDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`clip_draft_${clipId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearDraftFromStorage(clipId: string) {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(`clip_draft_${clipId}`);
  } catch {}
}

export const useEditorStore = create<EditorState>((set, get) => ({
  doc: null,
  serverVersion: 1,
  initialDoc: null,
  edl: null,

  history: [],
  future: [],

  isDirty: false,
  saveStatus: "idle",
  saveError: null,
  conflictServerDoc: null,
  lastSavedAt: null,

  localDraftAvailable: null,

  currentTimeMs: 0,
  isPlaying: false,
  playbackRate: 1.0,
  loopRange: true,
  showSafeZone: false,
  activeTab: "transcript",

  init: (record: ClipEditRecord) => {
    const doc = record.doc;
    const edl = EditDecisionList.create(doc.range.start_ms, doc.range.end_ms, doc.removals);

    // Check for newer local draft
    const draft = loadDraftFromStorage(doc.clip_id);
    let draftAvailable: LocalDraft | null = null;
    if (draft && draft.timestamp > new Date(record.created_at).getTime()) {
      // Draft has different edits
      draftAvailable = draft;
    }

    set({
      doc,
      serverVersion: record.version,
      initialDoc: JSON.parse(JSON.stringify(doc)),
      edl,
      history: [],
      future: [],
      isDirty: false,
      saveStatus: "saved",
      saveError: null,
      conflictServerDoc: null,
      currentTimeMs: doc.range.start_ms,
      localDraftAvailable: draftAvailable,
      lastSavedAt: Date.now(),
    });

    instrumentation.recordEvent("editor_open", doc.clip_id, {
      version: record.version,
      has_draft: Boolean(draftAvailable),
    });
  },

  setDocDirect: (newDoc: ClipEditDoc) => {
    const edl = EditDecisionList.create(newDoc.range.start_ms, newDoc.range.end_ms, newDoc.removals);
    set({ doc: newDoc, edl, isDirty: true });
    get().triggerAutosave();
  },

  canUndo: () => get().history.length > 0,
  canRedo: () => get().future.length > 0,

  undo: () => {
    const { doc, history, future } = get();
    if (!doc || history.length === 0) return;

    const prevDoc = history[history.length - 1];
    const newHistory = history.slice(0, history.length - 1);
    const newFuture = [doc, ...future];
    const edl = EditDecisionList.create(prevDoc.range.start_ms, prevDoc.range.end_ms, prevDoc.removals);

    set({
      doc: prevDoc,
      edl,
      history: newHistory,
      future: newFuture,
      isDirty: true,
    });

    saveDraftToStorage(prevDoc.clip_id, prevDoc);
    instrumentation.recordEvent("undo", prevDoc.clip_id);
    get().triggerAutosave();
  },

  redo: () => {
    const { doc, history, future } = get();
    if (!doc || future.length === 0) return;

    const nextDoc = future[0];
    const newFuture = future.slice(1);
    const newHistory = [...history, doc].slice(-HISTORY_LIMIT);
    const edl = EditDecisionList.create(nextDoc.range.start_ms, nextDoc.range.end_ms, nextDoc.removals);

    set({
      doc: nextDoc,
      edl,
      history: newHistory,
      future: newFuture,
      isDirty: true,
    });

    saveDraftToStorage(nextDoc.clip_id, nextDoc);
    instrumentation.recordEvent("redo", nextDoc.clip_id);
    get().triggerAutosave();
  },

  setRange: (range) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      range: { ...range },
    };
    const edl = EditDecisionList.create(range.start_ms, range.end_ms, doc.removals);

    set({
      doc: newDoc,
      edl,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("trim_boundary", doc.clip_id, { range });
    get().triggerAutosave();
  },

  addManualRemoval: ({ start_ms, end_ms, text }) => {
    const { doc, history } = get();
    if (!doc) return;

    const removal: ClipEditRemoval = {
      id: typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `rem_${Date.now()}`,
      start_ms,
      end_ms,
      kind: "manual",
      enabled: true,
      text: text || null,
    };

    const newRemovals = [...doc.removals, removal].sort((a, b) => a.start_ms - b.start_ms);
    const newDoc: ClipEditDoc = {
      ...doc,
      removals: newRemovals,
    };
    const edl = EditDecisionList.create(doc.range.start_ms, doc.range.end_ms, newRemovals);

    set({
      doc: newDoc,
      edl,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("delete_word", doc.clip_id, { removal });
    get().triggerAutosave();
  },

  toggleRemoval: (id) => {
    const { doc, history } = get();
    if (!doc) return;

    const newRemovals = doc.removals.map((r) =>
      r.id === id ? { ...r, enabled: !r.enabled } : r
    );
    const newDoc: ClipEditDoc = {
      ...doc,
      removals: newRemovals,
    };
    const edl = EditDecisionList.create(doc.range.start_ms, doc.range.end_ms, newRemovals);

    set({
      doc: newDoc,
      edl,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("toggle_cleanup", doc.clip_id, { removal_id: id });
    get().triggerAutosave();
  },

  removeRemoval: (id) => {
    const { doc, history } = get();
    if (!doc) return;

    const newRemovals = doc.removals.filter((r) => r.id !== id);
    const newDoc: ClipEditDoc = {
      ...doc,
      removals: newRemovals,
    };
    const edl = EditDecisionList.create(doc.range.start_ms, doc.range.end_ms, newRemovals);

    set({
      doc: newDoc,
      edl,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("undo_removal", doc.clip_id, { removal_id: id });
    get().triggerAutosave();
  },

  setCleanupOptions: (options) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      cleanup_options: {
        ...doc.cleanup_options,
        ...options,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("toggle_cleanup_options", doc.clip_id, { options });
    get().triggerAutosave();
  },

  updateWordText: (wordIdx, text) => {
    const { doc, history } = get();
    if (!doc) return;

    const newWords = doc.captions.words.map((w, idx) =>
      idx === wordIdx ? { ...w, text } : w
    );
    const newDoc: ClipEditDoc = {
      ...doc,
      captions: {
        ...doc.captions,
        words: newWords,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("caption_text_edit", doc.clip_id, { wordIdx, text });
    get().triggerAutosave();
  },

  toggleWordEmphasis: (wordIdx) => {
    const { doc, history } = get();
    if (!doc) return;

    const newWords = doc.captions.words.map((w, idx) =>
      idx === wordIdx ? { ...w, emphasis: !w.emphasis } : w
    );
    const newDoc: ClipEditDoc = {
      ...doc,
      captions: {
        ...doc.captions,
        words: newWords,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("toggle_emphasis", doc.clip_id, { wordIdx });
    get().triggerAutosave();
  },

  deleteWordRange: (start_ms, end_ms, text) => {
    get().addManualRemoval({ start_ms, end_ms, text });
  },

  setCaptionStyle: (styleKey) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      captions: {
        ...doc.captions,
        style_key: styleKey,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("style_change", doc.clip_id, { styleKey });
    get().triggerAutosave();
  },

  setCaptionStyleOverrides: (overrides) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      captions: {
        ...doc.captions,
        style_overrides: {
          ...doc.captions.style_overrides,
          ...overrides,
        },
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    get().triggerAutosave();
  },

  setCaptionEnabled: (enabled) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      captions: {
        ...doc.captions,
        enabled,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    get().triggerAutosave();
  },

  setReframeKeyframes: (keyframes) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      reframe: {
        ...doc.reframe,
        keyframes,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("reframe_edit", doc.clip_id, { count: keyframes.length });
    get().triggerAutosave();
  },

  setReframeModeOverride: (segmentKey, mode) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = {
      ...doc,
      reframe: {
        ...doc.reframe,
        mode_overrides: {
          ...(doc.reframe.mode_overrides || {}),
          [segmentKey]: mode,
        },
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    get().triggerAutosave();
  },

  setHook: (hook) => {
    const { doc, history } = get();
    if (!doc) return;

    // When swapping hook, adjust start_ms to hook start
    const newDoc: ClipEditDoc = {
      ...doc,
      hook,
      range: {
        ...doc.range,
        start_ms: hook.start_ms,
      },
    };
    const edl = EditDecisionList.create(hook.start_ms, doc.range.end_ms, doc.removals);

    set({
      doc: newDoc,
      edl,
      currentTimeMs: hook.start_ms,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });

    saveDraftToStorage(doc.clip_id, newDoc);
    instrumentation.recordEvent("swap_hook", doc.clip_id, { hook });
    get().triggerAutosave();
  },

  setPresetKey: (presetKey) => {
    const { doc, history } = get();
    if (!doc) return;

    const newDoc: ClipEditDoc = { ...doc, preset_key: presetKey };
    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });
    saveDraftToStorage(doc.clip_id, newDoc);
    get().triggerAutosave();
  },

  setBrandConfig: (brandUpdate) => {
    const { doc, history } = get();
    if (!doc) return;

    const currentBrand = doc.brand || {
      kit_id: null,
      apply_logo: true,
      apply_intro: true,
      apply_outro: true,
      apply_style: true,
    };

    const newDoc: ClipEditDoc = {
      ...doc,
      brand: {
        ...currentBrand,
        ...brandUpdate,
      },
    };

    set({
      doc: newDoc,
      history: [...history, doc].slice(-HISTORY_LIMIT),
      future: [],
      isDirty: true,
    });
    saveDraftToStorage(doc.clip_id, newDoc);
    get().triggerAutosave();
  },

  setCurrentTimeMs: (currentTimeMs) => set({ currentTimeMs }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
  setPlaybackRate: (playbackRate) => set({ playbackRate }),
  setLoopRange: (loopRange) => set({ loopRange }),
  setShowSafeZone: (showSafeZone) => set({ showSafeZone }),
  setActiveTab: (activeTab) => set({ activeTab }),

  triggerAutosave: () => {
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout);
    }
    autosaveTimeout = setTimeout(() => {
      get().save(false, "autosave");
    }, 800);
  },

  save: async (isCheckpoint = false, label = "autosave") => {
    const { doc, serverVersion } = get();
    if (!doc) return false;

    set({ saveStatus: "saving", saveError: null });

    try {
      const res = await api.saveClipEdit(
        doc.clip_id,
        { doc, is_checkpoint: isCheckpoint, label },
        serverVersion
      );

      set({
        doc: res.doc,
        serverVersion: res.version,
        isDirty: false,
        saveStatus: "saved",
        saveError: null,
        conflictServerDoc: null,
        lastSavedAt: Date.now(),
      });

      if (isCheckpoint) {
        clearDraftFromStorage(doc.clip_id);
      }

      return true;
    } catch (err: any) {
      if (err instanceof ApiError && err.code === "VERSION_CONFLICT") {
        set({
          saveStatus: "conflict",
          saveError: err.message,
          conflictServerDoc: err.server_doc || null,
        });
      } else {
        set({
          saveStatus: "error",
          saveError: err?.message || "Failed to save edits",
        });
      }
      return false;
    }
  },

  resolveConflictKeepMine: async () => {
    const { doc, conflictServerDoc } = get();
    if (!doc) return;
    const serverVer = conflictServerDoc?.version || (get().serverVersion + 1);
    set({ serverVersion: serverVer, conflictServerDoc: null });
    await get().save(true, "conflict_overwrite");
  },

  resolveConflictUseServer: () => {
    const { conflictServerDoc } = get();
    if (!conflictServerDoc) return;
    const edl = EditDecisionList.create(
      conflictServerDoc.range.start_ms,
      conflictServerDoc.range.end_ms,
      conflictServerDoc.removals
    );
    set({
      doc: conflictServerDoc,
      serverVersion: conflictServerDoc.version,
      edl,
      isDirty: false,
      saveStatus: "saved",
      saveError: null,
      conflictServerDoc: null,
    });
    clearDraftFromStorage(conflictServerDoc.clip_id);
  },

  restoreLocalDraft: () => {
    const { localDraftAvailable } = get();
    if (!localDraftAvailable) return;
    const draftDoc = localDraftAvailable.doc;
    const edl = EditDecisionList.create(
      draftDoc.range.start_ms,
      draftDoc.range.end_ms,
      draftDoc.removals
    );
    set({
      doc: draftDoc,
      edl,
      isDirty: true,
      localDraftAvailable: null,
    });
    get().triggerAutosave();
  },

  discardLocalDraft: () => {
    const { doc } = get();
    if (doc) clearDraftFromStorage(doc.clip_id);
    set({ localDraftAvailable: null });
  },

  resetToAuto: async () => {
    const { doc } = get();
    if (!doc) return;
    set({ saveStatus: "saving" });
    try {
      const res = await api.resetEditToAuto(doc.clip_id);
      const edl = EditDecisionList.create(
        res.doc.range.start_ms,
        res.doc.range.end_ms,
        res.doc.removals
      );
      set({
        doc: res.doc,
        serverVersion: res.version,
        edl,
        isDirty: false,
        saveStatus: "saved",
        saveError: null,
        history: [],
        future: [],
      });
      clearDraftFromStorage(doc.clip_id);
    } catch (err: any) {
      set({ saveStatus: "error", saveError: err?.message || "Failed to reset" });
    }
  },
}));
