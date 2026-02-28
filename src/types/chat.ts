export type MessageRole = 'user' | 'assistant';
export type AgentType = 'blitz' | 'vibecoder' | 'chat' | 'bounce' | 'queue' | 'bid' | null;

export interface CallStatus {
  business: string;
  phone?: string;
  address?: string;
  rating?: number;
  status: 'pending' | 'ringing' | 'connected' | 'complete' | 'failed' | 'no_answer' | 'busy';
  result?: string;
  error?: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  agent?: AgentType;
  sessionId?: string;
  callStatuses?: CallStatus[];
  isThinking?: boolean;
  thinkingTime?: number;
}

/** Returns true if the agent type is a "coming soon" agent that isn't implemented yet. */
export function isComingSoonAgent(agent: AgentType): agent is 'bounce' | 'queue' | 'bid' {
  return agent === 'bounce' || agent === 'queue' || agent === 'bid';
}

/** Returns true if the given timestamp should show relative to the previous one (>5 min gap). */
export function shouldShowTimestamp(current: Date, previous: Date | null): boolean {
  if (!previous) return true;
  const diffMs = current.getTime() - previous.getTime();
  return diffMs > 5 * 60 * 1000;
}

/** Format a timestamp as HH:MM for display. */
export function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
