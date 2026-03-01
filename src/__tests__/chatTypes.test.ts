import { describe, it, expect } from 'vitest';
import { isComingSoonAgent } from '../types/chat';
import type { AgentType } from '../types/chat';

describe('isComingSoonAgent', () => {
  it('returns true for bounce agent', () => {
    expect(isComingSoonAgent('bounce')).toBe(true);
  });

  it('returns true for queue agent', () => {
    expect(isComingSoonAgent('queue')).toBe(true);
  });

  it('returns true for bid agent', () => {
    expect(isComingSoonAgent('bid')).toBe(true);
  });

  it('returns false for blitz agent', () => {
    expect(isComingSoonAgent('blitz')).toBe(false);
  });

  it('returns false for vibecoder agent', () => {
    expect(isComingSoonAgent('vibecoder')).toBe(false);
  });

  it('returns false for chat agent', () => {
    expect(isComingSoonAgent('chat')).toBe(false);
  });

  it('returns false for null agent', () => {
    expect(isComingSoonAgent(null)).toBe(false);
  });
});
