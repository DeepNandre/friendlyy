import { useState, useRef, useEffect, useCallback } from 'react';
import { Sparkles } from 'lucide-react';
import { useBlitzStream, CallStatusType } from '../hooks/useBlitzStream';
import type { Message, CallStatus, AgentType } from '../types/chat';
import { isComingSoonAgent, shouldShowTimestamp, formatTimestamp } from '../types/chat';

import ChatSidebar from '../components/chat/ChatSidebar';
import WelcomeState from '../components/chat/WelcomeState';
import BlitzCallWidget from '../components/chat/BlitzCallWidget';
import VibeCoderWidget from '../components/chat/VibeCoderWidget';
import ComingSoonCard from '../components/chat/ComingSoonCard';
import ChatInput from '../components/chat/ChatInput';
import DetailPanel from '../components/chat/DetailPanel';

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';

function mapCallStatus(status: CallStatusType): CallStatus['status'] {
  switch (status) {
    case 'pending': return 'pending';
    case 'ringing': return 'ringing';
    case 'connected': case 'speaking': case 'recording': return 'connected';
    case 'complete': return 'complete';
    case 'no_answer': return 'no_answer';
    case 'busy': return 'busy';
    case 'failed': return 'failed';
    default: return 'pending';
  }
}

export default function AIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [detailPanelMessageId, setDetailPanelMessageId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const stream = useBlitzStream(activeSessionId);

  // Smart scroll: only auto-scroll when user is near bottom
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
  }, []);

  useEffect(() => {
    if (isNearBottomRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
    }
  }, [messages]);

  // SSE stream → message updates
  useEffect(() => {
    if (!activeMessageId || !activeSessionId) return;

    const mappedStatuses: CallStatus[] = stream.callStatuses.map((cs) => ({
      business: cs.business,
      phone: cs.phone,
      address: cs.address,
      rating: cs.rating,
      status: mapCallStatus(cs.status),
      result: cs.result,
      error: cs.error,
    }));

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== activeMessageId) return msg;
        let content = msg.content;
        if (stream.sessionStatus === 'searching') content = 'Searching for businesses near you...';
        else if (stream.sessionStatus === 'calling') content = `Found ${stream.callStatuses.length} businesses. Making calls now...`;
        else if (stream.sessionStatus === 'complete' && stream.summary) content = stream.summary;
        else if (stream.sessionStatus === 'error') content = stream.error || 'Something went wrong.';
        return {
          ...msg,
          content,
          isThinking: false,
          callStatuses: mappedStatuses.length > 0 ? mappedStatuses : msg.callStatuses,
        };
      })
    );

    if (stream.sessionStatus === 'complete' || stream.sessionStatus === 'error') {
      setIsLoading(false);
      setActiveSessionId(null);
      setActiveMessageId(null);
    }
  }, [stream, activeMessageId, activeSessionId]);

  // Core send logic — single source of truth for sending messages
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    const thinkingMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: thinkingMessageId, role: 'assistant', content: '', timestamp: new Date(), isThinking: true },
    ]);

    try {
      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim() }),
      });
      if (!response.ok) throw new Error('Failed');
      const data = await response.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id !== thinkingMessageId
            ? msg
            : {
                ...msg,
                content: data.message,
                agent: data.agent as AgentType,
                sessionId: data.session_id,
                isThinking: false,
                thinkingTime: 2,
                callStatuses: data.agent === 'blitz' ? [] : undefined,
              }
        )
      );

      if (data.agent === 'blitz' && data.session_id) {
        setActiveSessionId(data.session_id);
        setActiveMessageId(thinkingMessageId);
      } else {
        setIsLoading(false);
      }
    } catch {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id !== thinkingMessageId
            ? msg
            : { ...msg, content: "Sorry, I couldn't process that. Please try again.", isThinking: false }
        )
      );
      setIsLoading(false);
    }
  }, [isLoading]);

  // Thin wrapper for input-based sending
  const handleSend = useCallback(() => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput('');
    sendMessage(text);
  }, [input, sendMessage]);

  const handleViewDetails = useCallback((messageId: string) => {
    setDetailPanelMessageId(messageId);
    setDetailPanelOpen(true);
  }, []);

  const detailMessage = detailPanelMessageId
    ? messages.find((m) => m.id === detailPanelMessageId)
    : null;

  return (
    <div className="h-screen bg-background flex overflow-hidden">
      <ChatSidebar />

      <main
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto flex flex-col relative"
      >
        <div className="flex-1 px-4 md:px-20 lg:px-36 py-12 flex flex-col">
          {messages.length === 0 && <WelcomeState onSendMessage={sendMessage} />}

          <div className="flex flex-col gap-7 max-w-2xl w-full mx-auto">
            {messages.map((message, msgIdx) => {
              const prevMessage = msgIdx > 0 ? messages[msgIdx - 1] : null;
              const showTimestamp = shouldShowTimestamp(
                message.timestamp,
                prevMessage?.timestamp ?? null
              );

              return (
                <div key={message.id} className="flex flex-col gap-2 animate-slide-up">
                  {/* Timestamp */}
                  {showTimestamp && (
                    <div className="text-center">
                      <span className="text-[11px] text-muted-foreground/60 font-sans">
                        {formatTimestamp(message.timestamp)}
                      </span>
                    </div>
                  )}

                  {/* User message */}
                  {message.role === 'user' && (
                    <div className="flex items-start gap-3.5">
                      <div className="w-8 h-8 rounded-full bg-foreground text-background flex items-center justify-center text-xs font-semibold font-sans shrink-0 mt-0.5">
                        U
                      </div>
                      <p className="text-[15px] text-foreground leading-relaxed font-sans pt-1">
                        {message.content}
                      </p>
                    </div>
                  )}

                  {/* Assistant message */}
                  {message.role === 'assistant' && (
                    <div className="flex flex-col gap-3 pl-11 min-h-[40px]">
                      {message.isThinking ? (
                        <div className="flex items-center gap-2 text-muted-foreground text-sm font-sans">
                          <div className="flex gap-1">
                            {[0, 150, 300].map((delay) => (
                              <div
                                key={delay}
                                className="w-1.5 h-1.5 bg-foreground/40 rounded-full animate-bounce"
                                style={{ animationDelay: `${delay}ms` }}
                              />
                            ))}
                          </div>
                          <span>Thinking...</span>
                        </div>
                      ) : (
                        <>
                          {message.thinkingTime && (
                            <div className="text-muted-foreground text-xs font-sans font-medium flex items-center gap-1.5">
                              <Sparkles size={11} />
                              Thought for {message.thinkingTime}s
                            </div>
                          )}
                          <p className="text-[15px] text-foreground leading-relaxed font-sans">
                            {message.content}
                          </p>

                          {/* Coming Soon Card */}
                          {isComingSoonAgent(message.agent) && (
                            <ComingSoonCard
                              agent={message.agent}
                              message={message.content}
                              onSendMessage={sendMessage}
                            />
                          )}

                          {/* Blitz Call Widget */}
                          {message.agent === 'blitz' && message.callStatuses && message.callStatuses.length > 0 && (
                            <BlitzCallWidget
                              callStatuses={message.callStatuses}
                              sessionComplete={!activeSessionId || message.id !== activeMessageId}
                              onViewDetails={() => handleViewDetails(message.id)}
                            />
                          )}

                          {/* VibeCoder / Build Widget */}
                          {(message.agent === 'vibecoder' || message.agent === 'build') && <VibeCoderWidget />}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          <div className="h-28 shrink-0" />
        </div>

        <ChatInput
          input={input}
          isLoading={isLoading}
          onInputChange={setInput}
          onSend={handleSend}
        />
      </main>

      {/* Detail Panel */}
      <DetailPanel
        open={detailPanelOpen}
        onOpenChange={setDetailPanelOpen}
        message={detailMessage ?? null}
      />
    </div>
  );
}
