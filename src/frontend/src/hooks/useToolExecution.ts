import { useCallback, useState } from "react";
import { ApiError, api } from "@/services/api";
import type { ExecutionStatus } from "@/types/tool";

export function useToolExecution() {
  const [status, setStatus] = useState<ExecutionStatus>("idle");
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);

  const executingRef = { current: false };

  const execute = useCallback(async (toolName: string, params: Record<string, unknown>) => {
    // Guard: prevent concurrent execution (double-click protection)
    if (executingRef.current) return;
    executingRef.current = true;

    setStatus("running");
    setError(null);
    setData(null);
    setDuration(null);

    try {
      const result = await api<{
        result: { success: boolean; data: unknown; error: string | null; duration_ms: number };
      }>(`/tools/${toolName}/execute`, {
        method: "POST",
        body: params,
      });

      setDuration(result.result.duration_ms);
      if (result.result.success) {
        setData(result.result.data);
        setStatus("completed");
      } else {
        setError(result.result.error ?? "Unknown error");
        setStatus("error");
      }
      return result;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Network error";
      setError(message);
      setStatus("error");
      throw err;
    } finally {
      executingRef.current = false;
    }
  }, []);

  const reset = useCallback(() => {
    executingRef.current = false;
    setStatus("idle");
    setData(null);
    setError(null);
    setDuration(null);
  }, []);

  return { status, data, error, duration, execute, reset };
}
