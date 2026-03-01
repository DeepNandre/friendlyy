import React, { useRef, useEffect } from 'react';
import { Sparkles, ArrowRight, Loader2 } from 'lucide-react';

interface ChatInputProps {
  input: string;
  isLoading: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
}

export default function ChatInput({ input, isLoading, onInputChange, onSend }: ChatInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  return (
    <div className="sticky bottom-0 bg-gradient-to-t from-background via-background/95 to-transparent pt-6 pb-5 px-4 md:px-20 lg:px-36">
      <div className="max-w-2xl mx-auto">
        <div className="bg-card border border-border rounded-2xl shadow-lg shadow-foreground/8 flex items-center p-2 gap-2">
          <div className="pl-2 text-accent">
            <Sparkles size={17} />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSend()}
            placeholder="Ask me anything... Find services, build apps, get quotes"
            className="flex-1 outline-none text-sm text-foreground placeholder-muted-foreground bg-transparent min-w-0 py-2 font-sans"
            disabled={isLoading}
          />
          <button
            onClick={onSend}
            disabled={!input.trim() || isLoading}
            className="bg-foreground hover:opacity-80 disabled:opacity-30 disabled:cursor-not-allowed text-background rounded-xl w-10 h-10 flex items-center justify-center shrink-0 transition-all"
          >
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
          </button>
        </div>
        <p className="text-center text-[11px] text-muted-foreground mt-2 font-sans">
          Friendly AI can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  );
}
