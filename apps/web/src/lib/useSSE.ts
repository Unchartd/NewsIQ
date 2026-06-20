import { useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface PipelineSSEEvent {
  run_id: string;
  stage: string;
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
  latency_ms?: number;
  error?: string;
  timestamp: string;
}

export function useSSE() {
  const [lastEvent, setLastEvent] = useState<PipelineSSEEvent | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");

  useEffect(() => {
    setStatus("connecting");
    const sseUrl = `${API_BASE_URL}/admin/pipeline/stream`;
    const eventSource = new EventSource(sseUrl, { withCredentials: true });

    eventSource.onopen = () => {
      setStatus("connected");
    };

    eventSource.onmessage = (event) => {
      try {
        const parsed: PipelineSSEEvent = JSON.parse(event.data);
        setLastEvent(parsed);
      } catch (err) {
        console.error("Failed to parse SSE event data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE connection error:", err);
      setStatus("disconnected");
    };

    return () => {
      eventSource.close();
      setStatus("disconnected");
    };
  }, []);

  return { lastEvent, status };
}
