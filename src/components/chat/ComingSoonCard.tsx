import { Hammer, Clock, TrendingDown, Sparkles } from 'lucide-react';
import type { AgentType } from '../../types/chat';

interface ComingSoonCardProps {
  agent: 'bounce' | 'queue' | 'bid';
  message: string;
  onSendMessage: (text: string) => void;
}

const AGENT_CONFIG: Record<'bounce' | 'queue' | 'bid', {
  icon: React.ReactNode;
  label: string;
  suggestion: string;
  suggestionPrompt: string;
}> = {
  bounce: {
    icon: <Hammer size={16} />,
    label: 'Cancel Subscriptions',
    suggestion: 'Find a service instead',
    suggestionPrompt: 'Find me a plumber who can come today',
  },
  queue: {
    icon: <Clock size={16} />,
    label: 'Wait on Hold',
    suggestion: 'Get quotes instead',
    suggestionPrompt: 'Get quotes from 3 electricians near me',
  },
  bid: {
    icon: <TrendingDown size={16} />,
    label: 'Negotiate Bills',
    suggestion: 'Find a better deal instead',
    suggestionPrompt: 'Find me the cheapest broadband providers near me',
  },
};

export default function ComingSoonCard({ agent, message, onSendMessage }: ComingSoonCardProps) {
  const config = AGENT_CONFIG[agent];

  return (
    <div className="border border-accent/30 rounded-2xl bg-accent/10 overflow-hidden mt-1">
      <div className="px-4 py-3 flex items-center gap-2 border-b border-accent/20">
        <div className="bg-accent text-accent-foreground p-1.5 rounded-lg">
          {config.icon}
        </div>
        <span className="font-semibold text-foreground text-sm font-sans">{config.label}</span>
        <span className="ml-auto text-xs text-muted-foreground font-sans bg-accent/30 px-2 py-0.5 rounded-full">
          Coming Soon
        </span>
      </div>
      <div className="p-4">
        <p className="text-sm text-foreground font-sans leading-relaxed">{message}</p>
        <button
          onClick={() => onSendMessage(config.suggestionPrompt)}
          className="mt-3 bg-card hover:bg-muted border border-border px-3.5 py-2 rounded-full text-xs text-foreground font-sans font-medium transition-all hover:shadow-sm flex items-center gap-1.5"
        >
          <Sparkles size={11} className="text-accent" />
          {config.suggestion}
        </button>
      </div>
    </div>
  );
}
