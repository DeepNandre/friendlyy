import { describe, it, expect } from 'vitest';
import { shouldShowTimestamp, formatTimestamp } from '../types/chat';

describe('shouldShowTimestamp', () => {
  it('returns true when there is no previous timestamp', () => {
    const now = new Date('2025-01-15T10:30:00');
    expect(shouldShowTimestamp(now, null)).toBe(true);
  });

  it('returns true when gap is more than 5 minutes', () => {
    const prev = new Date('2025-01-15T10:00:00');
    const current = new Date('2025-01-15T10:05:01'); // 5 min 1 sec
    expect(shouldShowTimestamp(current, prev)).toBe(true);
  });

  it('returns false when gap is less than 5 minutes', () => {
    const prev = new Date('2025-01-15T10:00:00');
    const current = new Date('2025-01-15T10:04:59'); // 4 min 59 sec
    expect(shouldShowTimestamp(current, prev)).toBe(false);
  });

  it('returns false when gap is exactly 5 minutes', () => {
    const prev = new Date('2025-01-15T10:00:00');
    const current = new Date('2025-01-15T10:05:00');
    expect(shouldShowTimestamp(current, prev)).toBe(false);
  });

  it('returns false for messages within the same minute', () => {
    const prev = new Date('2025-01-15T10:00:00');
    const current = new Date('2025-01-15T10:00:30');
    expect(shouldShowTimestamp(current, prev)).toBe(false);
  });

  it('handles large time gaps (hours apart)', () => {
    const prev = new Date('2025-01-15T10:00:00');
    const current = new Date('2025-01-15T14:00:00');
    expect(shouldShowTimestamp(current, prev)).toBe(true);
  });
});

describe('formatTimestamp', () => {
  it('formats a date as HH:MM', () => {
    const date = new Date('2025-01-15T14:30:00');
    const result = formatTimestamp(date);
    // Result format depends on locale, but should contain hours and minutes
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });
});
