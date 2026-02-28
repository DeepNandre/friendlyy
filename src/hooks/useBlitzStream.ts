/**
 * Hook for consuming Blitz SSE stream
 * Provides real-time call status updates
 */

import { useState, useEffect, useCallback } from "react";

export type CallStatusType =
  | "pending"
  | "ringing"
  | "connected"
  | "speaking"
  | "recording"
  | "complete"
  | "no_answer"
  | "busy"
  | "failed";

export interface CallStatus {
  business: string;
  phone?: string;
  status: CallStatusType;
  result?: string;
  error?: string;
}

export interface BlitzStreamState {
  isConnected: boolean;
  sessionStatus: "idle" | "searching" | "calling" | "complete" | "error";
  callStatuses: CallStatus[];
  businesses: Array<{ name: string; phone: string; address?: string }>;
  summary: string | null;
  error: string | null;
}

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || "http://localhost:8000";
const BLITZ_STREAM_PATH = import.meta.env.VITE_BLITZ_STREAM_PATH || "/api/blitz/stream";

const buildStreamUrl = (sessionId: string): string => {
  if (BLITZ_STREAM_PATH.includes(":sessionId")) {
    return `${BLITZ_API_BASE}${BLITZ_STREAM_PATH.replace(":sessionId", sessionId)}`;
  }

  const normalizedPath = BLITZ_STREAM_PATH.endsWith("/")
    ? BLITZ_STREAM_PATH.slice(0, -1)
    : BLITZ_STREAM_PATH;
  return `${BLITZ_API_BASE}${normalizedPath}/${sessionId}`;
};

export function useBlitzStream(sessionId: string | null) {
  const [state, setState] = useState<BlitzStreamState>({
    isConnected: false,
    sessionStatus: "idle",
    callStatuses: [],
    businesses: [],
    summary: null,
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

    // Handle session_start
    eventSource.addEventListener("session_start", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        sessionStatus: data.status,
        businesses: data.businesses || [],
        callStatuses:
          data.businesses?.map((b: any) => ({
            business: b.name,
            phone: b.phone,
            status: "pending" as CallStatusType,
          })) || [],
      }));
    });

    // Handle status updates
    eventSource.addEventListener("status", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        sessionStatus: data.status,
        businesses: data.businesses || prev.businesses,
        callStatuses:
          data.businesses?.map((b: any) => ({
            business: b.name,
            phone: b.phone,
            status: "pending" as CallStatusType,
          })) || prev.callStatuses,
      }));
    });

    // Handle call_started
    eventSource.addEventListener("call_started", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        callStatuses: prev.callStatuses.map((c) =>
          c.business === data.business
            ? { ...c, status: "ringing" as CallStatusType }
            : c
        ),
      }));
    });

    // Handle call_connected
    eventSource.addEventListener("call_connected", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        callStatuses: prev.callStatuses.map((c) =>
          c.business === data.business
            ? { ...c, status: "connected" as CallStatusType }
            : c
        ),
      }));
    });

    // Handle call_result
    eventSource.addEventListener("call_result", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        callStatuses: prev.callStatuses.map((c) =>
          c.business === data.business
            ? {
                ...c,
                status: "complete" as CallStatusType,
                result: data.result,
              }
            : c
        ),
      }));
    });

    // Handle call_failed
    eventSource.addEventListener("call_failed", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        callStatuses: prev.callStatuses.map((c) =>
          c.business === data.business
            ? {
                ...c,
                status: "failed" as CallStatusType,
                error: data.error || "No answer",
              }
            : c
        ),
      }));
    });

    // Handle session_complete
    eventSource.addEventListener("session_complete", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        sessionStatus: "complete",
        summary: data.summary,
        callStatuses:
          data.results?.map((r: any) => ({
            business: r.business,
            status: r.status as CallStatusType,
            result: r.result,
          })) || prev.callStatuses,
      }));
      eventSource.close();
    });

    // Handle error
    eventSource.addEventListener("error", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setState((prev) => ({
          ...prev,
          sessionStatus: "error",
          error: data.message,
        }));
      } catch {
        setState((prev) => ({
          ...prev,
          sessionStatus: "error",
          error: "Unknown error",
        }));
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
      sessionStatus: "idle",
      callStatuses: [],
      businesses: [],
      summary: null,
      error: null,
    });
  }, []);

  return { ...state, reset };
}
