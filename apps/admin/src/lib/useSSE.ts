import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

export type SSEStatus = "connecting" | "connected" | "disconnected" | "error";

export interface PipelineSSEEvent {
  run_id: string;
  stage: string;
  status: "pending" | "running" | "success" | "failed" | "skipped";
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

interface UseSSEReturn {
  status: SSEStatus;
  lastEvent: PipelineSSEEvent | null;
  events: PipelineSSEEvent[];
  clearEvents: () => void;
}

export function useSSE(): UseSSEReturn {
  const [status, setStatus] = useState<SSEStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<PipelineSSEEvent | null>(null);
  const [events, setEvents] = useState<PipelineSSEEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(1000);
  // Last Redis stream id seen. The backend emits `id:` on every frame and
  // accepts either the Last-Event-ID header or a last_id query parameter, so it
  // can resume exactly where the client left off. A browser only sends
  // Last-Event-ID on its own automatic reconnect; because onerror closes the
  // connection and builds a *new* EventSource, that header is never sent and
  // every event during the outage was lost. Passing the id explicitly is what
  // makes a 30-second disconnect recoverable rather than a silent gap.
  const lastIdRef = useRef<string | null>(null);

  function connect() {
    if (typeof window === "undefined") return;

    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("newsiq_admin_token")
        : null;

    const params = new URLSearchParams();
    if (token) params.set("token", token);
    if (lastIdRef.current) params.set("last_id", lastIdRef.current);
    const query = params.toString();
    const url = `${API_BASE_URL}/admin/pipeline/stream${query ? `?${query}` : ""}`;

    const es = new EventSource(url);
    esRef.current = es;
    setStatus("connecting");

    es.onopen = () => {
      setStatus("connected");
      retryDelay.current = 1000;
    };

    es.onmessage = (event) => {
      // Record the stream position before parsing, so a malformed payload does
      // not cause the same event to be replayed forever on the next reconnect.
      if (event.lastEventId) lastIdRef.current = event.lastEventId;
      try {
        const data = JSON.parse(event.data) as PipelineSSEEvent;
        setLastEvent(data);
        setEvents((prev) => [data, ...prev].slice(0, 200));
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      es.close();
      setStatus("disconnected");
      // Exponential backoff reconnect (max 30s)
      retryRef.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 2, 30000);
        connect();
      }, retryDelay.current);
    };
  }

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    status,
    lastEvent,
    events,
    clearEvents: () => setEvents([]),
  };
}
