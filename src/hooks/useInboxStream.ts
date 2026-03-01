/**
 * Hook for consuming Inbox agent SSE stream.
 * Provides real-time inbox check progress updates.
 */

import { useState, useEffect, useCallback } from "react";

export interface InboxSummary {
  important_count: number;
  top_updates: string[];
  needs_action: boolean;
  draft_replies_available: boolean;
  sender_highlights?: string[];
  time_range?: string;
}

export type InboxStatus =
  | "idle"
  | "checking"
  | "auth_required"
  | "fetching"
  | "summarizing"
  | "complete"
  | "error";

export interface InboxStreamState {
  isConnected: boolean;
  inboxStatus: InboxStatus;
  message: string | null;
  authUrl: string | null;
  emailCount: number | null;
  summary: InboxSummary | null;
  error: string | null;
}

const API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

export function useInboxStream(sessionId: string | null) {
  const [state, setState] = useState<InboxStreamState>({
    isConnected: false,
    inboxStatus: "idle",
    message: null,
    authUrl: null,
    emailCount: null,
    summary: null,
    error: null,
  });

  useEffect(() => {
    if (!sessionId) return;

    const eventSource = new EventSource(
      `${API_BASE}/api/inbox/stream/${sessionId}`
    );

    eventSource.onopen = () => {
      setState((prev) => ({ ...prev, isConnected: true }));
    };

    eventSource.onerror = () => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        error: prev.inboxStatus === "complete" ? null : "Connection lost",
      }));
      eventSource.close();
    };

    eventSource.addEventListener("inbox_start", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "checking",
        message: data.message,
      }));
    });

    eventSource.addEventListener("inbox_auth_required", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "auth_required",
        message: data.message,
        authUrl: data.auth_url,
      }));
      eventSource.close();
    });

    eventSource.addEventListener("inbox_fetching", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "fetching",
        message: data.message,
      }));
    });

    eventSource.addEventListener("inbox_summarizing", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "summarizing",
        message: data.message,
        emailCount: data.email_count ?? prev.emailCount,
      }));
    });

    eventSource.addEventListener("inbox_complete", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "complete",
        message: data.message,
        summary: data.summary,
      }));
      eventSource.close();
    });

    eventSource.addEventListener("inbox_error", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        inboxStatus: "error",
        error: data.message,
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
      inboxStatus: "idle",
      message: null,
      authUrl: null,
      emailCount: null,
      summary: null,
      error: null,
    });
  }, []);

  return { ...state, reset };
}
