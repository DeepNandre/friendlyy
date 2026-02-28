import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBlitzStream } from '../hooks/useBlitzStream';

// Mock EventSource
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

describe('useBlitzStream', () => {
  it('returns idle state when sessionId is null', () => {
    const { result } = renderHook(() => useBlitzStream(null));

    expect(result.current.isConnected).toBe(false);
    expect(result.current.sessionStatus).toBe('idle');
    expect(result.current.callStatuses).toEqual([]);
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('creates EventSource when sessionId is provided', () => {
    renderHook(() => useBlitzStream('test-session'));

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.latest().url).toContain('test-session');
  });

  it('sets isConnected to true on open', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateOpen();
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('handles connection errors', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateError();
    });

    expect(result.current.isConnected).toBe(false);
    expect(result.current.error).toBe('Connection lost');
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('handles session_start with businesses including address and rating', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [
          { name: 'Plumber A', phone: '111-111', address: '123 Main St', rating: 4.5 },
          { name: 'Plumber B', phone: '222-222', address: '456 Oak Ave', rating: 3.8 },
        ],
      });
    });

    expect(result.current.sessionStatus).toBe('calling');
    expect(result.current.callStatuses).toHaveLength(2);
    expect(result.current.callStatuses[0]).toEqual({
      business: 'Plumber A',
      phone: '111-111',
      address: '123 Main St',
      rating: 4.5,
      status: 'pending',
    });
    expect(result.current.callStatuses[1].address).toBe('456 Oak Ave');
  });

  it('matches calls by phone number (primary key)', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [
          { name: 'Plumber A', phone: '111-111' },
          { name: 'Plumber B', phone: '222-222' },
        ],
      });
    });

    // Match by phone, even if business name differs slightly
    act(() => {
      MockEventSource.latest().simulateEvent('call_started', {
        business: 'Plumber A (different name)',
        phone: '111-111',
      });
    });

    expect(result.current.callStatuses[0].status).toBe('ringing');
    expect(result.current.callStatuses[1].status).toBe('pending');
  });

  it('falls back to business name matching when phone is missing', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [
          { name: 'Plumber A', phone: '111-111' },
        ],
      });
    });

    // Match by name when no phone in event data
    act(() => {
      MockEventSource.latest().simulateEvent('call_started', {
        business: 'Plumber A',
      });
    });

    expect(result.current.callStatuses[0].status).toBe('ringing');
  });

  it('handles call_connected event', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('call_connected', {
        business: 'Plumber A',
        phone: '111-111',
      });
    });

    expect(result.current.callStatuses[0].status).toBe('connected');
  });

  it('handles call_result event', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('call_result', {
        business: 'Plumber A',
        phone: '111-111',
        result: 'Available tomorrow, £95',
      });
    });

    expect(result.current.callStatuses[0].status).toBe('complete');
    expect(result.current.callStatuses[0].result).toBe('Available tomorrow, £95');
  });

  it('handles call_failed event', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('call_failed', {
        business: 'Plumber A',
        phone: '111-111',
        error: 'Line busy',
      });
    });

    expect(result.current.callStatuses[0].status).toBe('failed');
    expect(result.current.callStatuses[0].error).toBe('Line busy');
  });

  it('defaults error to "No answer" when call_failed has no error message', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('call_failed', {
        business: 'Plumber A',
        phone: '111-111',
      });
    });

    expect(result.current.callStatuses[0].error).toBe('No answer');
  });

  it('handles session_complete and preserves metadata', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [
          { name: 'Plumber A', phone: '111-111', address: '123 Main St', rating: 4.5 },
        ],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('session_complete', {
        summary: 'Found 1 plumber',
        results: [
          { business: 'Plumber A', phone: '111-111', status: 'complete', result: 'Available' },
        ],
      });
    });

    expect(result.current.sessionStatus).toBe('complete');
    expect(result.current.summary).toBe('Found 1 plumber');
    // Address/rating should be preserved from session_start
    expect(result.current.callStatuses[0].address).toBe('123 Main St');
    expect(result.current.callStatuses[0].rating).toBe(4.5);
    expect(MockEventSource.latest().closed).toBe(true);
  });

  it('handles session_complete without results (preserves existing statuses)', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('session_complete', {
        summary: 'Done',
      });
    });

    expect(result.current.sessionStatus).toBe('complete');
    expect(result.current.callStatuses).toHaveLength(1);
  });

  it('handles error event with parseable data', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      const errorEvent = { data: JSON.stringify({ message: 'Session timeout' }) } as MessageEvent;
      MockEventSource.latest().listeners['error']?.forEach((fn) => fn(errorEvent));
    });

    expect(result.current.sessionStatus).toBe('error');
    expect(result.current.error).toBe('Session timeout');
  });

  it('handles error event with unparseable data', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      const errorEvent = { data: 'not json' } as MessageEvent;
      MockEventSource.latest().listeners['error']?.forEach((fn) => fn(errorEvent));
    });

    expect(result.current.sessionStatus).toBe('error');
    expect(result.current.error).toBe('Unknown error');
  });

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useBlitzStream('test-session'));
    const es = MockEventSource.latest();

    expect(es.closed).toBe(false);
    unmount();
    expect(es.closed).toBe(true);
  });

  it('resets state via reset function', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    expect(result.current.callStatuses).toHaveLength(1);

    act(() => {
      result.current.reset();
    });

    expect(result.current.callStatuses).toEqual([]);
    expect(result.current.sessionStatus).toBe('idle');
  });

  it('handles empty businesses array in session_start', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'searching',
      });
    });

    expect(result.current.callStatuses).toEqual([]);
    expect(result.current.sessionStatus).toBe('searching');
  });

  it('does not match calls when neither phone nor name matches', () => {
    const { result } = renderHook(() => useBlitzStream('test-session'));

    act(() => {
      MockEventSource.latest().simulateEvent('session_start', {
        status: 'calling',
        businesses: [{ name: 'Plumber A', phone: '111-111' }],
      });
    });

    act(() => {
      MockEventSource.latest().simulateEvent('call_started', {
        business: 'Unknown Business',
        phone: '999-999',
      });
    });

    // Status should remain pending since nothing matched
    expect(result.current.callStatuses[0].status).toBe('pending');
  });
});
