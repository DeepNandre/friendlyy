import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Home,
  Sparkles,
  Phone,
  Code,
  Settings,
  ArrowRight,
  Check,
  X,
  Clock,
  Loader2,
  ChevronRight,
  Zap,
  MessageSquare,
  ExternalLink,
} from 'lucide-react';
import { useBlitzStream, CallStatusType } from '../hooks/useBlitzStream';
import { useBuildStream } from '../hooks/useBuildStream';

type MessageRole = 'user' | 'assistant';
type AgentType = 'blitz' | 'build' | 'chat' | null;

interface CallStatus {
  business: string;
  phone?: string;
  address?: string;
  status: 'pending' | 'ringing' | 'connected' | 'complete' | 'failed' | 'no_answer' | 'busy';
  result?: string;
  error?: string;
}

interface BuildStep {
  id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'complete' | 'error';
}

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  agent?: AgentType;
  sessionId?: string;
  callStatuses?: CallStatus[];
  isThinking?: boolean;
  thinkingTime?: number;
  previewUrl?: string;
  buildSteps?: BuildStep[];
}

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function AIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [activeBuildSessionId, setActiveBuildSessionId] = useState<string | null>(null);
  const [activeBuildMessageId, setActiveBuildMessageId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const stream = useBlitzStream(activeSessionId);
  const buildStream = useBuildStream(activeBuildSessionId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!activeMessageId || !activeSessionId) return;

    const mappedStatuses: CallStatus[] = stream.callStatuses.map((cs) => ({
      business: cs.business,
      phone: cs.phone,
      address: cs.address,
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
        return { ...msg, content, isThinking: false, callStatuses: mappedStatuses.length > 0 ? mappedStatuses : msg.callStatuses };
      })
    );

    if (stream.sessionStatus === 'complete' || stream.sessionStatus === 'error') {
      setIsLoading(false);
      setActiveSessionId(null);
      setActiveMessageId(null);
    }
  }, [stream, activeMessageId, activeSessionId]);

  // Handle build stream updates
  useEffect(() => {
    if (!activeBuildMessageId || !activeBuildSessionId) return;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== activeBuildMessageId) return msg;
        let content = msg.content;
        if (buildStream.buildStatus === 'building') {
          content = buildStream.message || 'Building your site...';
        } else if (buildStream.buildStatus === 'complete') {
          content = `${buildStream.message || 'Your site is ready!'}\n\n[View Preview](${buildStream.previewUrl})`;
        } else if (buildStream.buildStatus === 'clarification') {
          content = buildStream.clarification || 'Could you tell me more about what you want to build?';
        } else if (buildStream.buildStatus === 'error') {
          content = buildStream.error || 'Something went wrong while building.';
        }
        return {
          ...msg,
          content,
          isThinking: false,
          previewUrl: buildStream.previewUrl,
          buildSteps: buildStream.steps,
        };
      })
    );

    if (buildStream.buildStatus === 'complete' || buildStream.buildStatus === 'error' || buildStream.buildStatus === 'clarification') {
      setIsLoading(false);
      setActiveBuildSessionId(null);
      setActiveBuildMessageId(null);
    }
  }, [buildStream, activeBuildMessageId, activeBuildSessionId]);

  const mapCallStatus = (status: CallStatusType): CallStatus['status'] => {
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
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input.trim(), timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    const messageText = input.trim();
    setInput('');
    setIsLoading(true);

    const thinkingMessageId = (Date.now() + 1).toString();
    setMessages((prev) => [...prev, { id: thinkingMessageId, role: 'assistant', content: '', timestamp: new Date(), isThinking: true }]);

    try {
      // Build conversation history from previous messages (last 10 for context)
      const conversationHistory = messages
        .slice(-10)
        .filter((m) => !m.isThinking)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageText,
          conversation_history: conversationHistory,
        }),
      });
      if (!response.ok) throw new Error('Failed');
      const data = await response.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id !== thinkingMessageId ? msg : {
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
      } else if (data.agent === 'build' && data.session_id) {
        setActiveBuildSessionId(data.session_id);
        setActiveBuildMessageId(thinkingMessageId);
      } else {
        setIsLoading(false);
      }
    } catch {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id !== thinkingMessageId ? msg : { ...msg, content: "Sorry, I couldn't process that. Please try again.", isThinking: false }
        )
      );
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: CallStatus['status']) => {
    switch (status) {
      case 'pending': return <Clock size={15} />;
      case 'ringing': return <Phone size={15} className="animate-pulse" />;
      case 'connected': return <Loader2 size={15} className="animate-spin" />;
      case 'complete': return <Check size={15} />;
      default: return <X size={15} />;
    }
  };

  const getStatusText = (status: CallStatus['status']) => {
    const map: Record<CallStatus['status'], string> = {
      pending: 'Waiting...', ringing: 'Ringing...', connected: 'On call...',
      complete: 'Done', failed: 'Failed', no_answer: 'No answer', busy: 'Busy'
    };
    return map[status] || '';
  };

  return (
    <div className="h-screen bg-background flex overflow-hidden">

      {/* Sidebar */}
      <aside className="w-16 border-r border-border flex flex-col items-center py-6 gap-5 bg-background shrink-0">
        <Link
          to="/"
          className="w-9 h-9 rounded-2xl bg-background flex items-center justify-center p-1.5 shadow-lg border border-border overflow-hidden hover:bg-muted/50 transition-colors block"
          aria-label="Go to home"
        >
          <img src="/friendly-logo-monochrome.jpg" alt="Friendly" className="w-full h-full object-contain" />
        </Link>
        <div className="flex flex-col gap-1 mt-2">
          <button className="p-2.5 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground">
            <Home size={17} />
          </button>
          <button className="p-2.5 bg-accent rounded-xl transition-colors text-accent-foreground">
            <MessageSquare size={17} />
          </button>
          <button className="p-2.5 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground">
            <Phone size={17} />
          </button>
          <button className="p-2.5 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground">
            <Code size={17} />
          </button>
        </div>
        <button className="mt-auto text-muted-foreground hover:text-foreground transition-colors">
          <Settings size={17} />
        </button>
      </aside>

      {/* Chat Area */}
      <main className="flex-1 overflow-y-auto flex flex-col relative">
        <div className="flex-1 px-8 md:px-20 lg:px-36 py-12 flex flex-col">

          {/* Welcome State */}
          {messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center max-w-lg mx-auto gap-6 min-h-[60vh]">
              <div className="w-20 h-20 rounded-[22px] bg-background flex items-center justify-center p-2 shadow-2xl shadow-foreground/20 border border-border overflow-hidden">
                <img src="/friendly-logo-monochrome.jpg" alt="Friendly" className="w-full h-full object-contain" />
              </div>
              <div>
                <h1 className="text-4xl font-serif text-foreground mb-3">Hey, I'm Friendly</h1>
                <p className="text-base text-muted-foreground font-sans leading-relaxed">
                  I can help you find services, make calls, and build apps. What do you need?
                </p>
              </div>
              <div className="flex flex-wrap gap-2.5 justify-center mt-2">
                {[
                  { icon: <Phone size={13} />, label: 'Find a plumber', value: 'Find me a plumber who can come tomorrow' },
                  { icon: <Code size={13} />, label: 'Build a landing page', value: 'Build me a landing page for my startup' },
                  { icon: <Zap size={13} />, label: 'Get electrician quotes', value: 'Get quotes from 3 electricians in London' },
                ].map((action) => (
                  <button
                    key={action.label}
                    onClick={() => setInput(action.value)}
                    className="bg-card hover:bg-muted border border-border px-4 py-2.5 rounded-full text-sm text-foreground font-sans font-medium transition-all hover:shadow-sm flex items-center gap-2"
                  >
                    <span className="text-muted-foreground">{action.icon}</span>
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="flex flex-col gap-7 max-w-2xl w-full mx-auto">
            {messages.map((message) => (
              <div key={message.id} className="flex flex-col gap-2 animate-slide-up">

                {/* User */}
                {message.role === 'user' && (
                  <div className="flex items-start gap-3.5">
                    <div className="w-8 h-8 rounded-full bg-background flex items-center justify-center p-1 shrink-0 mt-0.5 border border-border overflow-hidden">
                      <img src="/friendly-logo-monochrome.jpg" alt="You" className="w-full h-full object-contain" />
                    </div>
                    <p className="text-[15px] text-foreground leading-relaxed font-sans pt-1">{message.content}</p>
                  </div>
                )}

                {/* Assistant */}
                {message.role === 'assistant' && (
                  <div className="flex flex-col gap-3 pl-11">
                    {message.isThinking ? (
                      <div className="flex items-center gap-2 text-muted-foreground text-sm font-sans">
                        <div className="flex gap-1">
                          {[0, 150, 300].map((delay) => (
                            <div key={delay} className="w-1.5 h-1.5 bg-foreground/40 rounded-full animate-bounce" style={{ animationDelay: `${delay}ms` }} />
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
                        <p className="text-[15px] text-foreground leading-relaxed font-sans">{message.content}</p>

                        {/* Blitz Call Widget - macOS FaceTime Style */}
                        {message.agent === 'blitz' && message.callStatuses && message.callStatuses.length > 0 && (() => {
                          const completedCalls = message.callStatuses.filter(c => c.status === 'complete');
                          const firstSuccessIdx = message.callStatuses.findIndex(c => c.status === 'complete' && c.result);

                          return (
                            <div className="w-full max-w-3xl mx-auto rounded-xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)] border border-gray-200/80 bg-[#f5f6f8] overflow-hidden text-gray-800 font-sans mt-3">

                              {/* Header */}
                              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200/80 bg-white/50 backdrop-blur-sm">
                                <div className="flex items-center gap-2">
                                  {/* FaceTime Icon */}
                                  <div className="w-7 h-7 rounded-lg bg-gradient-to-b from-[#44D955] to-[#34C759] flex items-center justify-center shadow-sm">
                                    <svg width="16" height="12" viewBox="0 0 16 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                                      <path d="M12 2.5C12 1.67157 11.3284 1 10.5 1H2.5C1.67157 1 1 1.67157 1 2.5V9.5C1 10.3284 1.67157 11 2.5 11H10.5C11.3284 11 12 10.3284 12 9.5V2.5Z" fill="white"/>
                                      <path d="M15.5 3.5L12.5 5.5V6.5L15.5 8.5C15.7761 8.68406 16 8.48528 16 8.15535V3.84465C16 3.51472 15.7761 3.31594 15.5 3.5Z" fill="white"/>
                                    </svg>
                                  </div>
                                  <span className="font-semibold text-[17px] text-gray-900 tracking-tight">FaceTime</span>
                                </div>
                                <span className="text-sm text-gray-500 font-medium">{completedCalls.length}/{message.callStatuses.length} complete</span>
                              </div>

                              {/* List Container */}
                              <div className="flex flex-col">
                                {message.callStatuses.map((call, idx) => {
                                  const isSuccess = call.status === 'complete' && call.result;
                                  const isBestOption = idx === firstSuccessIdx;
                                  const isFailed = call.status === 'failed' || call.status === 'no_answer' || call.status === 'busy';
                                  const isLast = idx === message.callStatuses.length - 1;

                                  return (
                                    <div key={idx} className={`flex justify-between items-start px-4 py-4 ${!isLast ? 'border-b border-gray-200/80' : ''}`}>
                                      <div className="flex flex-col gap-1">
                                        <div className="flex items-center gap-2">
                                          <span className="text-[15px] text-gray-900">{call.business}</span>
                                          {isBestOption && (
                                            <span className="px-2 py-0.5 text-[11px] font-semibold bg-[#FFD60A] text-black rounded-full shadow-sm">
                                              Best option
                                            </span>
                                          )}
                                        </div>
                                        {call.phone && (
                                          <div className="flex items-center gap-2">
                                            {isSuccess ? (
                                              <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                              </svg>
                                            ) : isFailed ? (
                                              <svg className="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                              </svg>
                                            ) : (
                                              <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />
                                            )}
                                            <span className="text-[13px] text-gray-500">{call.phone}</span>
                                          </div>
                                        )}
                                        {call.address && (
                                          <span className="text-[13px] text-gray-500 mt-0.5">{call.address}</span>
                                        )}
                                      </div>
                                      <div className="flex flex-col items-end gap-3">
                                        {call.result ? (
                                          <span className="text-[14px] text-gray-900">{call.result}</span>
                                        ) : isFailed ? (
                                          <span className="text-[14px] text-gray-500">No answer</span>
                                        ) : (
                                          <span className="text-[14px] text-gray-500">{getStatusText(call.status)}</span>
                                        )}
                                        {isSuccess && (
                                          <div className="flex gap-2">
                                            <a
                                              href={`tel:${call.phone}`}
                                              className="flex items-center gap-1.5 px-3 py-1 bg-[#F9F9FB] border border-gray-300/80 rounded-full text-[13px] text-gray-700 font-medium hover:bg-gray-100 transition-colors shadow-sm"
                                            >
                                              <svg className="w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                                              </svg>
                                              Call them
                                            </a>
                                            <button className="flex items-center gap-1.5 px-3 py-1 bg-[#F9F9FB] border border-gray-300/80 rounded-full text-[13px] text-gray-700 font-medium hover:bg-gray-100 transition-colors shadow-sm">
                                              <svg className="w-3.5 h-3.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                              </svg>
                                              Details
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })()}

                        {/* VibeCoder Widget */}
                        {message.agent === 'build' && (
                          <div className="border border-border rounded-2xl bg-card overflow-hidden mt-3 shadow-sm">
                            <div className="flex justify-between items-center px-4 py-3 bg-gradient-to-r from-violet-500/10 to-purple-500/10 border-b border-border">
                              <div className="flex items-center gap-2">
                                <div className="bg-gradient-to-br from-violet-500 to-purple-600 text-white p-1.5 rounded-lg">
                                  <Code size={13} />
                                </div>
                                <span className="font-semibold text-foreground text-sm font-sans">VibeCoder</span>
                              </div>
                              {message.previewUrl && (
                                <a
                                  href={message.previewUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-violet-600 font-medium font-sans flex items-center gap-1 hover:opacity-70 transition-opacity"
                                >
                                  View Preview <ExternalLink size={11} />
                                </a>
                              )}
                            </div>

                            {/* Build Steps */}
                            {message.buildSteps && message.buildSteps.length > 0 && (
                              <div className="px-4 py-3 space-y-2">
                                {message.buildSteps.map((step) => (
                                  <div key={step.id} className="flex items-center gap-2">
                                    {step.status === 'complete' ? (
                                      <Check size={14} className="text-green-500" />
                                    ) : step.status === 'in_progress' ? (
                                      <Loader2 size={14} className="text-violet-500 animate-spin" />
                                    ) : step.status === 'error' ? (
                                      <X size={14} className="text-red-500" />
                                    ) : (
                                      <Clock size={14} className="text-muted-foreground" />
                                    )}
                                    <span className={`text-sm font-sans ${step.status === 'complete' ? 'text-foreground' : 'text-muted-foreground'}`}>
                                      {step.label}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Preview iframe */}
                            {message.previewUrl && (
                              <div className="border-t border-border">
                                <iframe
                                  src={message.previewUrl}
                                  className="w-full h-64 bg-white"
                                  title="Website Preview"
                                />
                              </div>
                            )}

                            {/* Actions */}
                            {message.previewUrl && (
                              <div className="flex items-center gap-2 px-4 py-3 border-t border-border">
                                <a
                                  href={message.previewUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-white font-sans font-medium flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 hover:opacity-90 transition-opacity"
                                >
                                  <ExternalLink size={11} />
                                  Open Full Preview
                                </a>
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="h-28 shrink-0" />
        </div>

        {/* Floating Input */}
        <div className="sticky bottom-0 bg-gradient-to-t from-background via-background/95 to-transparent pt-6 pb-5 px-8 md:px-20 lg:px-36">
          <div className="max-w-2xl mx-auto">
            <div className="bg-card border border-border rounded-2xl shadow-lg shadow-foreground/8 flex items-center p-2 gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask me anything... Find services, build apps, get quotes"
                className="flex-1 outline-none text-sm text-foreground placeholder-muted-foreground bg-transparent min-w-0 py-2 pl-3 font-sans"
                disabled={isLoading}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="bg-foreground hover:opacity-80 disabled:opacity-30 disabled:cursor-not-allowed text-background rounded-xl w-9 h-9 flex items-center justify-center shrink-0 transition-all"
              >
                {isLoading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
              </button>
            </div>
            <p className="text-center text-[11px] text-muted-foreground mt-2 font-sans">
              Friendly AI can make mistakes. Verify important information.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
