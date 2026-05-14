import { useRef, useCallback, useState } from "react";
import type { ExecutionStatus, PingResult, PingSummary } from "@/types/tool";

interface UseWebSocketOptions {
  toolName: string;
}

interface WebSocketMessage {
  type: "result" | "notice" | "complete" | "error";
  seq?: number;
  data?: unknown;
  message_key?: string;
  message?: string;
}

export function useWebSocket({ toolName }: UseWebSocketOptions) {
  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [results, setResults] = useState<PingResult[]>([]);
  const [summary, setSummary] = useState<PingSummary | null>(null);
  const [terminatedBy, setTerminatedBy] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const cancelledRef = useRef(false);

  const connect = useCallback(
    (params: Record<string, unknown>) => {
      cancelledRef.current = false;
      setStatus("running");
      setResults([]);
      setSummary(null);
      setTerminatedBy(null);
      setDuration(null);
      setError(null);

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/v1/tools/${toolName}/stream`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "start", params }));
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);

          switch (msg.type) {
            case "result":
              if (cancelledRef.current) return;
              setResults((prev) => [
                ...prev,
                { ...(msg.data as PingResult), seq: msg.seq ?? (prev.length + 1) },
              ]);
              break;
            case "complete": {
              const completeData = msg.data as {
                summary: PingSummary;
                duration_ms: number;
                terminated_by: string;
              };
              setSummary(completeData.summary);
              setDuration(completeData.duration_ms);
              setTerminatedBy(completeData.terminated_by);
              setStatus(completeData.terminated_by === "user" ? "stopped" : "completed");
              break;
            }
            case "error":
              setError(msg.message ?? "Unknown error");
              setStatus("error");
              break;
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        if (!cancelledRef.current) {
          setError("WebSocket connection error");
          setStatus("error");
        }
      };

      ws.onclose = () => {
        if (!cancelledRef.current && status === "running") {
          setStatus("completed");
        }
      };
    },
    [toolName],
  );

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
    }
  }, []);

  const reset = useCallback(() => {
    cancelledRef.current = true;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("idle");
    setResults([]);
    setSummary(null);
    setTerminatedBy(null);
    setDuration(null);
    setError(null);
  }, []);

  return {
    status,
    results,
    summary,
    terminatedBy,
    duration,
    error,
    connect,
    cancel,
    reset,
  };
}
