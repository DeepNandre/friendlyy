/**
 * Hook for consuming Build agent SSE stream.
 * Provides real-time build progress updates.
 */

import { useState, useEffect, useCallback } from "react";

export interface BuildStep {
  id: string;
  label: string;
  status: "pending" | "in_progress" | "complete" | "error";
}

export interface BuildStreamState {
  isConnected: boolean;
  buildStatus: "idle" | "building" | "complete" | "error" | "clarification";
  message: string | null;
  steps: BuildStep[];
  previewUrl: string | null;
  previewId: string | null;
  clarification: string | null;
  error: string | null;
}

const API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

export function useBuildStream(sessionId: string | null) {
  const [state, setState] = useState<BuildStreamState>({
    isConnected: false,
    buildStatus: "idle",
    message: null,
    steps: [],
    previewUrl: null,
    previewId: null,
    clarification: null,
    error: null,
  });

  useEffect(() => {
    if (!sessionId) return;

    const eventSource = new EventSource(
      `${API_BASE}/api/build/stream/${sessionId}`
    );

    eventSource.onopen = () => {
      setState((prev) => ({ ...prev, isConnected: true }));
    };

    eventSource.onerror = () => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        error: prev.buildStatus === "complete" ? null : "Connection lost",
      }));
      eventSource.close();
    };

    // Build started - receive initial step list
    eventSource.addEventListener("build_started", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        buildStatus: "building",
        message: data.message,
        steps: data.steps || [],
      }));
    });

    // Build progress - a step completed, next one started
    eventSource.addEventListener("build_progress", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        message: data.message,
        steps: prev.steps.map((s) => {
          if (s.id === data.completed_step) return { ...s, status: "complete" };
          if (s.id === data.step) return { ...s, status: "in_progress" };
          return s;
        }),
      }));
    });

    // Build complete - preview URL available
    eventSource.addEventListener("build_complete", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        buildStatus: "complete",
        message: data.message,
        previewUrl: data.preview_url,
        previewId: data.preview_id,
        steps: prev.steps.map((s) =>
          s.id === data.completed_step || s.status === "in_progress"
            ? { ...s, status: "complete" }
            : s
        ),
      }));
      eventSource.close();
    });

    // Build error
    eventSource.addEventListener("build_error", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        buildStatus: "error",
        error: data.message,
        steps: prev.steps.map((s) =>
          s.status === "in_progress" ? { ...s, status: "error" } : s
        ),
      }));
      eventSource.close();
    });

    // Clarification needed
    eventSource.addEventListener("build_clarification", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        buildStatus: "clarification",
        clarification: data.message,
      }));
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  const reset = useCallback(() => {
    setState({
      isConnected: false,
      buildStatus: "idle",
      message: null,
      steps: [],
      previewUrl: null,
      previewId: null,
      clarification: null,
      error: null,
    });
  }, []);

  return { ...state, reset };
}
