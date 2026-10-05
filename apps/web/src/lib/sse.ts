import { useEffect, useState, useRef } from "react";
import { JobEventPayload } from "@clip-it-up/shared";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UseJobSSEOptions {
  jobId: string;
  token?: string | null;
  onEvent?: (payload: JobEventPayload) => void;
  onError?: (err: Error) => void;
  enabled?: boolean;
}

export function useJobSSE({ jobId, token, onEvent, onError, enabled = true }: UseJobSSEOptions) {
  const [data, setData] = useState<JobEventPayload | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !jobId) return;

    let isMounted = true;
    let retryTimeout: NodeJS.Timeout | null = null;

    async function connectSSE() {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const headers: Record<string, string> = {
          Accept: "text/event-stream",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        if (lastEventIdRef.current) {
          headers["Last-Event-ID"] = lastEventIdRef.current;
        }

        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/events`, {
          headers,
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`SSE stream connection failed: ${response.status} ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No response body received from SSE stream");
        }

        setIsConnected(true);
        setError(null);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (isMounted) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const block of lines) {
            if (!block.trim() || block.startsWith(":")) continue; // Skip comments/heartbeats

            let eventName = "message";
            let dataStr = "";
            let eventId: string | null = null;

            const blockLines = block.split("\n");
            for (const line of blockLines) {
              if (line.startsWith("event: ")) {
                eventName = line.replace("event: ", "").trim();
              } else if (line.startsWith("data: ")) {
                dataStr = line.replace("data: ", "").trim();
              } else if (line.startsWith("id: ")) {
                eventId = line.replace("id: ", "").trim();
              }
            }

            if (eventId) {
              lastEventIdRef.current = eventId;
            }

            if (dataStr) {
              try {
                const parsed: JobEventPayload = JSON.parse(dataStr);
                if (isMounted) {
                  setData(parsed);
                  onEvent?.(parsed);

                  if (["succeeded", "failed", "cancelled"].includes(parsed.status)) {
                    setIsConnected(false);
                    return; // Stream closed normally
                  }
                }
              } catch (parseErr) {
                console.warn("Failed to parse SSE payload:", parseErr);
              }
            }
          }
        }
      } catch (err: any) {
        if (controller.signal.aborted) return;
        if (isMounted) {
          setIsConnected(false);
          const errorObj = err instanceof Error ? err : new Error(String(err));
          setError(errorObj);
          onError?.(errorObj);

          // Retry connection after 3 seconds
          retryTimeout = setTimeout(() => {
            if (isMounted) connectSSE();
          }, 3000);
        }
      }
    }

    connectSSE();

    return () => {
      isMounted = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (retryTimeout) {
        clearTimeout(retryTimeout);
      }
    };
  }, [jobId, token, enabled]);

  return { data, isConnected, error };
}
