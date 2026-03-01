import { useState, useEffect, useCallback, useRef } from 'react';

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type CallFriendPhase = 'initiating' | 'ringing' | 'connected' | 'complete' | 'failed' | 'no_answer';

export interface CallFriendTranscript {
  speaker: 'ai' | 'human' | 'system' | 'error';
  text: string;
  timestamp?: string;
}

export interface CallFriendStreamState {
  phase: CallFriendPhase | null;
  friendName: string | null;
  question: string | null;
  message: string | null;
  summary: string | null;
  response: string | null;
  transcripts: CallFriendTranscript[];
  error: string | null;
  isComplete: boolean;
}

export function useCallFriendStream(sessionId: string | null) {
  const [state, setState] = useState<CallFriendStreamState>({
    phase: null,
    friendName: null,
    question: null,
    message: null,
    summary: null,
    response: null,
    transcripts: [],
    error: null,
    isComplete: false,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setState({
        phase: null,
        friendName: null,
        question: null,
        message: null,
        summary: null,
        response: null,
        transcripts: [],
        error: null,
        isComplete: false,
      });
      return;
    }

    const url = `${BLITZ_API_BASE}/api/call_friend/stream/${sessionId}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('[CallFriend Stream] Connected:', sessionId);
    };

    eventSource.onerror = (error) => {
      console.error('[CallFriend Stream] Error:', error);
      setState((prev) => ({
        ...prev,
        error: 'Connection lost',
        isComplete: true,
      }));
      eventSource.close();
    };

    // Handle different event types
    eventSource.addEventListener('session_start', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: data.phase || 'initiating',
        friendName: data.friend_name,
        question: data.question,
      }));
    });

    eventSource.addEventListener('status', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: data.phase,
        message: data.message,
        friendName: data.friend_name || prev.friendName,
      }));
    });

    eventSource.addEventListener('call_started', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: 'ringing',
        message: data.message,
      }));
    });

    eventSource.addEventListener('call_connected', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: 'connected',
        message: data.message,
      }));
    });

    eventSource.addEventListener('transcript', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        transcripts: [
          ...prev.transcripts,
          {
            speaker: data.speaker,
            text: data.text,
            timestamp: data.timestamp,
          },
        ],
      }));
    });

    eventSource.addEventListener('session_complete', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: data.phase || 'complete',
        summary: data.summary,
        response: data.response,
        isComplete: true,
      }));
      eventSource.close();
    });

    eventSource.addEventListener('error', (event) => {
      const data = JSON.parse(event.data);
      setState((prev) => ({
        ...prev,
        phase: 'failed',
        error: data.message,
        isComplete: true,
      }));
      eventSource.close();
    });

    return () => {
      eventSource.close();
    };
  }, [sessionId]);

  return state;
}
