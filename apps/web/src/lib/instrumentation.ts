import { api } from "./api";
import { EditorEvent } from "@clip-it-up/shared";

class EditorInstrumentation {
  private queue: EditorEvent[] = [];
  private flushTimer: NodeJS.Timeout | null = null;
  private sessionId: string;
  private lastInteractionTime: number = Date.now();
  private totalHandsOnSeconds: number = 0;

  constructor() {
    this.sessionId = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", () => this.flushSync());
      window.addEventListener("pagehide", () => this.flushSync());
    }
  }

  getSessionId(): string {
    return this.sessionId;
  }

  getHandsOnSeconds(): number {
    return Math.round(this.totalHandsOnSeconds);
  }

  recordEvent(type: string, clipId?: string | null, payload: Record<string, any> = {}) {
    const now = Date.now();
    const gap = (now - this.lastInteractionTime) / 1000;
    // Active time heuristic: only accumulate if gap <= 20 seconds
    if (gap > 0 && gap <= 20) {
      this.totalHandsOnSeconds += gap;
    }
    this.lastInteractionTime = now;

    this.queue.push({
      session_id: this.sessionId,
      type,
      clip_id: clipId || null,
      payload: {
        ...payload,
        hands_on_seconds: Math.round(this.totalHandsOnSeconds),
      },
      created_at: new Date(now).toISOString(),
    });

    if (this.queue.length >= 10) {
      this.flush();
    } else if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => this.flush(), 2500);
    }
  }

  async flush() {
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    if (this.queue.length === 0) return;

    const toSend = [...this.queue];
    this.queue = [];

    try {
      await api.recordEditorEvents({ events: toSend });
    } catch (err) {
      // Re-queue on error up to 50 events
      this.queue = [...toSend.slice(-40), ...this.queue];
    }
  }

  private flushSync() {
    if (this.queue.length === 0) return;
    const toSend = [...this.queue];
    this.queue = [];
    const payload = JSON.stringify({ events: toSend });
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/editor/events`;
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(url, blob);
    }
  }
}

export const instrumentation = new EditorInstrumentation();
