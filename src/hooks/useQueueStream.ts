/**
 * Hook for consuming Queue agent SSE stream.
 * Provides real-time hold status updates.
 */

import { useState, useEffect, useCallback } from "react";

export type QueuePhase =
  | "idle"
  | "calling"
  | "ivr"
  | "hold"
  | "human_detected"
  | "failed"
  | "cancelled";

export interface QueueStreamState {
  isConnected: boolean;
  phase: QueuePhase;
  business: string | null;
  phone: string | null;
  holdElapsed: number;
  message: string | null;
  ivrStep: string | null;
  humanDetected: boolean;
  error: string | null;
}

const API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

const STREAM_PATH =
  import.meta.env.VITE_BLITZ_STREAM_PATH || "/api/blitz/stream";

const buildStreamUrl = (sessionId: string): string => {
  if (STREAM_PATH.includes(":sessionId")) {
    return `${API_BASE}${STREAM_PATH.replace(":sessionId", sessionId)}`;
  }
  const normalizedPath = STREAM_PATH.endsWith("/")
    ? STREAM_PATH.slice(0, -1)
    : STREAM_PATH;
  return `${API_BASE}${normalizedPath}/${sessionId}`;
};

export function useQueueStream(sessionId: string | null) {
  const [state, setState] = useState<QueueStreamState>({
    isConnected: false,
    phase: "idle",
    business: null,
    phone: null,
    holdElapsed: 0,
    message: null,
    ivrStep: null,
    humanDetected: false,
    error: null,
  });

  useEffect(() => {
    if (!sessionId) return;

    const eventSource = new EventSource(buildStreamUrl(sessionId));

    eventSource.onopen = () => {
      setState((prev) => ({ ...prev, isConnected: true }));
    };

    eventSource.onerror = () => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        error: "Connection lost",
      }));
      eventSource.close();
    };

    // Queue started — call is being placed
    eventSource.addEventListener("queue_started", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        phase: "calling",
        business: data.business || null,
        phone: data.phone || null,
        message: data.message,
      }));
    });

    // IVR navigation — navigating phone menu
    eventSource.addEventListener("queue_ivr", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        phase: "ivr",
        message: data.message,
        ivrStep: data.heard || data.step?.toString() || null,
      }));
    });

    // On hold — waiting for a human
    eventSource.addEventListener("queue_hold", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        phase: "hold",
        message: data.message,
        holdElapsed: data.elapsed || 0,
      }));
    });

    // Hold update — periodic status while waiting
    eventSource.addEventListener("queue_hold_update", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        message: data.message,
        holdElapsed: data.elapsed || prev.holdElapsed,
      }));
    });

    // Human detected — someone picked up!
    eventSource.addEventListener("queue_human_detected", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        phase: "human_detected",
        humanDetected: true,
        message: data.message,
        phone: data.phone || prev.phone,
        holdElapsed: data.hold_time || prev.holdElapsed,
      }));
      eventSource.close();
    });

    // Queue failed — call ended without reaching a human
    eventSource.addEventListener("queue_failed", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        phase: data.cancelled ? "cancelled" : "failed",
        message: data.message,
        error: data.error || null,
      }));
      eventSource.close();
    });

    // Generic error
    eventSource.addEventListener("error", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setState((prev) => ({
          ...prev,
          phase: "failed",
          error: data.message,
        }));
      } catch {
        // SSE connection error, not a data event
      }
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  const reset = useCallback(() => {
    setState({
      isConnected: false,
      phase: "idle",
      business: null,
      phone: null,
      holdElapsed: 0,
      message: null,
      ivrStep: null,
      humanDetected: false,
      error: null,
    });
  }, []);

  const cancel = useCallback(async () => {
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE}/api/queue/cancel/${sessionId}`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to cancel queue:", err);
    }
  }, [sessionId]);

  return { ...state, reset, cancel };
}
