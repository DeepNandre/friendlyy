import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useInboxStream } from '../hooks/useInboxStream';

// Mock EventSource (same pattern as useBlitzStream tests)
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (e: any) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  close() {
    this.closed = true;
  }

  // Test helpers
  simulateOpen() {
    this.onopen?.();
  }

  simulateError() {
    this.onerror?.();
  }

  simulateEvent(type: string, data: any) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    this.listeners[type]?.forEach((fn) => fn(event));
  }

  static reset() {
    MockEventSource.instances = [];
  }

  static latest(): MockEventSource {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }
}

beforeEach(() => {
  MockEventSource.reset();
  (global as any).EventSource = MockEventSource;
});

afterEach(() => {
  delete (global as any).EventSource;
});

describe('useInboxStream', () => {
  it('returns idle state when sessionId is null', () => {
    const { result } = renderHook(() => useInboxStream(null));

    expect(result.current.isConnected).toBe(false);
    expect(result.current.inboxStatus).toBe('idle');
    expect(result.current.summary).toBeNull();
    expect(result.current.authUrl).toBeNull();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('creates EventSource with correct URL when sessionId is provided', () => {
    renderHook(() => useInboxStream('inbox-session-123'));

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.latest().url).toContain('/api/inbox/stream/inbox-session-123');
  });

  it('sets isConnected to true on open', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateOpen();
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('handles inbox_start event → status becomes checking', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_start', {
        message: 'Checking your Gmail connection...',
      });
    });

    expect(result.current.inboxStatus).toBe('checking');
    expect(result.current.message).toBe('Checking your Gmail connection...');
    expect(MockEventSource.latest().closed).toBe(false);
  });

  it('handles inbox_auth_required event → status becomes auth_required, authUrl set, EventSource closed', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_auth_required', {
        message: 'Please connect your Gmail',
        auth_url: 'https://composio.dev/auth/gmail?entity=test-entity',
      });
    });

    expect(result.current.inboxStatus).toBe('auth_required');
    expect(result.current.authUrl).toBe('https://composio.dev/auth/gmail?entity=test-entity');
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('handles inbox_fetching event → status becomes fetching', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_fetching', {
        message: 'Fetching your recent emails...',
      });
    });

    expect(result.current.inboxStatus).toBe('fetching');
    expect(result.current.message).toBe('Fetching your recent emails...');
  });

  it('handles inbox_summarizing event → status becomes summarizing, emailCount set', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_summarizing', {
        message: 'Found 12 emails. Summarizing...',
        email_count: 12,
      });
    });

    expect(result.current.inboxStatus).toBe('summarizing');
    expect(result.current.emailCount).toBe(12);
  });

  it('handles inbox_complete event → status becomes complete, summary populated, EventSource closed', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    const mockSummary = {
      important_count: 3,
      top_updates: ['Meeting at 3pm', 'AWS bill due', 'PR approved'],
      needs_action: true,
      draft_replies_available: false,
      sender_highlights: ['Product Team', 'AWS'],
      time_range: 'last 24 hours',
    };

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_complete', {
        message: "Here's your inbox summary!",
        summary: mockSummary,
      });
    });

    expect(result.current.inboxStatus).toBe('complete');
    expect(result.current.summary).toEqual(mockSummary);
    expect(result.current.summary!.important_count).toBe(3);
    expect(result.current.summary!.top_updates).toHaveLength(3);
    expect(result.current.summary!.needs_action).toBe(true);
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('handles inbox_error event → status becomes error, error message set, EventSource closed', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_error', {
        message: 'Failed to fetch emails: API timeout',
      });
    });

    expect(result.current.inboxStatus).toBe('error');
    expect(result.current.error).toBe('Failed to fetch emails: API timeout');
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('handles connection errors', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateError();
    });

    expect(result.current.isConnected).toBe(false);
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useInboxStream('test-session'));
    const es = MockEventSource.latest();

    expect(es.closed).toBe(false);
    unmount();
    expect(es.closed).toBe(true);
  });

  it('resets state via reset function', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('inbox_complete', {
        message: 'Done!',
        summary: {
          important_count: 5,
          top_updates: ['Test'],
          needs_action: true,
          draft_replies_available: false,
        },
      });
    });

    expect(result.current.inboxStatus).toBe('complete');

    act(() => {
      result.current.reset();
    });

    expect(result.current.inboxStatus).toBe('idle');
    expect(result.current.summary).toBeNull();
    expect(result.current.authUrl).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.emailCount).toBeNull();
  });

  it('follows full event sequence: start → fetching → summarizing → complete', () => {
    const { result } = renderHook(() => useInboxStream('test-session'));
    const es = MockEventSource.latest();

    // Start
    act(() => es.simulateEvent('inbox_start', { message: 'Checking...' }));
    expect(result.current.inboxStatus).toBe('checking');

    // Fetching
    act(() => es.simulateEvent('inbox_fetching', { message: 'Fetching...' }));
    expect(result.current.inboxStatus).toBe('fetching');

    // Summarizing
    act(() => es.simulateEvent('inbox_summarizing', { message: 'Summarizing 5 emails...', email_count: 5 }));
    expect(result.current.inboxStatus).toBe('summarizing');
    expect(result.current.emailCount).toBe(5);

    // Complete
    act(() => es.simulateEvent('inbox_complete', {
      message: "Here's your summary!",
      summary: {
        important_count: 2,
        top_updates: ['Email from boss', 'Package delivered'],
        needs_action: true,
        draft_replies_available: false,
      },
    }));
    expect(result.current.inboxStatus).toBe('complete');
    expect(result.current.summary!.important_count).toBe(2);
    expect(es.closed).toBe(true);
  });
});
