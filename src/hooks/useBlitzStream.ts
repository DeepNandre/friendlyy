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
  address?: string;
  rating?: number;
  latitude?: number;
  longitude?: number;
  status: CallStatusType;
  result?: string;
  error?: string;
}

export interface TranscriptEntry {
  callId: string;
  speaker: "ai" | "human" | "system" | "error";
  text: string;
  timestamp: string;
}

export interface BlitzStreamState {
  isConnected: boolean;
  sessionStatus: "idle" | "searching" | "calling" | "complete" | "error";
  callStatuses: CallStatus[];
  businesses: Array<{ name: string; phone: string; address?: string; rating?: number; latitude?: number; longitude?: number }>;
  transcripts: TranscriptEntry[];
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

/** Match a call status entry by phone (primary) or business name (fallback). */
function matchesCall(call: CallStatus, data: { business?: string; phone?: string }): boolean {
  if (call.phone && data.phone && call.phone === data.phone) return true;
  return call.business === data.business;
}

/** Map business data from SSE events into CallStatus entries with metadata. */
function mapBusinessesToCallStatuses(businesses: any[]): CallStatus[] {
  return businesses.map((b) => ({
    business: b.name,
    phone: b.phone,
    address: b.address,
    rating: b.rating,
    latitude: b.latitude,
    longitude: b.longitude,
    status: "pending" as CallStatusType,
  }));
}

export function useBlitzStream(sessionId: string | null) {
  const [state, setState] = useState<BlitzStreamState>({
    isConnected: false,
    sessionStatus: "idle",
    callStatuses: [],
    businesses: [],
    transcripts: [],
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
      const businesses = data.businesses || [];
      setState((prev) => ({
        ...prev,
        sessionStatus: data.status,
        businesses,
        callStatuses: mapBusinessesToCallStatuses(businesses),
      }));
    });

    // Handle status updates
    eventSource.addEventListener("status", (e) => {
      const data = JSON.parse(e.data);
      const businesses = data.businesses;
      setState((prev) => ({
        ...prev,
        sessionStatus: data.status,
        businesses: businesses || prev.businesses,
        callStatuses: businesses
          ? mapBusinessesToCallStatuses(businesses)
          : prev.callStatuses,
      }));
    });

    // Handle call_started
    eventSource.addEventListener("call_started", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        callStatuses: prev.callStatuses.map((c) =>
          matchesCall(c, data)
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
          matchesCall(c, data)
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
          matchesCall(c, data)
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
          matchesCall(c, data)
            ? {
                ...c,
                status: "failed" as CallStatusType,
                error: data.error || "No answer",
              }
            : c
        ),
      }));
    });

    // Handle live transcript events
    eventSource.addEventListener("transcript", (e) => {
      const data = JSON.parse(e.data);
      const entry: TranscriptEntry = {
        callId: data.call_id,
        speaker: data.speaker,
        text: data.text,
        timestamp: data.timestamp,
      };
      setState((prev) => ({
        ...prev,
        transcripts: [...prev.transcripts, entry],
      }));
    });

    // Handle session_complete — preserve metadata from existing statuses
    eventSource.addEventListener("session_complete", (e) => {
      const data = JSON.parse(e.data);
      setState((prev) => {
        const updatedStatuses = data.results
          ? data.results.map((r: any) => {
              // Try to find existing status to preserve address/rating/phone
              const existing = prev.callStatuses.find((c) =>
                matchesCall(c, { business: r.business, phone: r.phone })
              );
              return {
                business: r.business,
                phone: existing?.phone || r.phone,
                address: existing?.address,
                rating: existing?.rating,
                status: r.status as CallStatusType,
                result: r.result,
                error: r.error,
              };
            })
          : prev.callStatuses;

        return {
          ...prev,
          sessionStatus: "complete",
          summary: data.summary,
          callStatuses: updatedStatuses,
        };
      });
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
      transcripts: [],
      summary: null,
      error: null,
    });
  }, []);

  return { ...state, reset };
}
