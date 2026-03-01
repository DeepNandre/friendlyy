import React, { useState, useRef, useEffect } from 'react';
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
} from 'lucide-react';
import { useBlitzStream, CallStatusType } from '../hooks/useBlitzStream';

type MessageRole = 'user' | 'assistant';
type AgentType = 'blitz' | 'vibecoder' | 'chat' | null;

interface CallStatus {
  business: string;
  phone?: string;
  status: 'pending' | 'ringing' | 'connected' | 'complete' | 'failed' | 'no_answer' | 'busy';
  result?: string;
  error?: string;
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
}

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function AIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const stream = useBlitzStream(activeSessionId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!activeMessageId || !activeSessionId) return;

    const mappedStatuses: CallStatus[] = stream.callStatuses.map((cs) => ({
      business: cs.business,
      phone: cs.phone,
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
      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
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
        <div className="w-9 h-9 rounded-2xl bg-foreground flex items-center justify-center text-background shadow-lg">
          <Zap size={16} />
        </div>
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
              <div className="w-20 h-20 rounded-[22px] bg-foreground flex items-center justify-center text-background shadow-2xl shadow-foreground/20">
                <Sparkles size={32} />
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
                    <div className="w-8 h-8 rounded-full bg-foreground text-background flex items-center justify-center text-xs font-semibold font-sans shrink-0 mt-0.5">
                      U
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

                        {/* Blitz Call Widget */}
                        {message.agent === 'blitz' && message.callStatuses && message.callStatuses.length > 0 && (
                          <div className="rounded-2xl bg-card overflow-hidden mt-2 shadow-md border border-border/60">
                            {/* Header */}
                            <div className="px-5 py-4 bg-gradient-to-r from-accent/40 to-accent/10 border-b border-border/60">
                              <div className="flex items-center gap-3">
                                <div className="bg-foreground text-background p-2 rounded-xl shadow-sm">
                                  <Phone size={14} />
                                </div>
                                <div>
                                  <h3 className="font-semibold text-foreground text-sm font-sans tracking-tight">Blitz Calls</h3>
                                  <p className="text-xs text-muted-foreground font-sans mt-0.5">
                                    {message.callStatuses.filter(c => c.status === 'complete').length} of {message.callStatuses.length} calls complete
                                  </p>
                                </div>
                              </div>
                              {/* Progress bar */}
                              <div className="mt-3 h-1 bg-border/50 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-foreground/80 rounded-full transition-all duration-500 ease-out"
                                  style={{
                                    width: `${(message.callStatuses.filter(c => ['complete', 'failed', 'no_answer', 'busy'].includes(c.status)).length / message.callStatuses.length) * 100}%`,
                                  }}
                                />
                              </div>
                            </div>
                            {/* Call list */}
                            <div className="divide-y divide-border/40">
                              {message.callStatuses.map((call, idx) => (
                                <div key={idx} className="flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors">
                                  <div className="flex items-center gap-3.5">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                                      call.status === 'complete' ? 'bg-emerald-500/10 text-emerald-600' :
                                      call.status === 'ringing' ? 'bg-amber-500/10 text-amber-500' :
                                      call.status === 'connected' ? 'bg-blue-500/10 text-blue-500' :
                                      call.status === 'failed' || call.status === 'no_answer' || call.status === 'busy' ? 'bg-destructive/10 text-destructive' :
                                      'bg-muted text-muted-foreground'
                                    }`}>
                                      {getStatusIcon(call.status)}
                                    </div>
                                    <div>
                                      <p className="text-sm font-medium text-foreground font-sans leading-tight">{call.business}</p>
                                      {call.phone && <p className="text-xs text-muted-foreground font-sans mt-0.5">{call.phone}</p>}
                                    </div>
                                  </div>
                                  <div className="text-right max-w-[45%]">
                                    {call.result ? (
                                      <span className="text-xs font-medium text-foreground bg-accent/50 px-2.5 py-1 rounded-full font-sans inline-block">{call.result}</span>
                                    ) : call.error ? (
                                      <span className="text-xs text-destructive font-sans">{call.error}</span>
                                    ) : (
                                      <span className="text-xs text-muted-foreground font-sans">{getStatusText(call.status)}</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* VibeCoder Widget */}
                        {message.agent === 'vibecoder' && (
                          <div className="border border-border rounded-2xl bg-card overflow-hidden mt-1 shadow-sm">
                            <div className="flex justify-between items-center px-4 py-3 bg-accent/20 border-b border-border">
                              <div className="flex items-center gap-2">
                                <div className="bg-foreground text-background p-1.5 rounded-lg">
                                  <Code size={13} />
                                </div>
                                <span className="font-semibold text-foreground text-sm font-sans">VibeCoder</span>
                              </div>
                              <button className="text-xs text-foreground font-medium font-sans flex items-center gap-1 hover:opacity-70 transition-opacity">
                                Open Editor <ChevronRight size={13} />
                              </button>
                            </div>
                            <div className="p-4 text-sm text-muted-foreground font-sans">
                              Ready to build your project. Click to open the VibeCoder editor.
                            </div>
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
              <div className="pl-2 text-accent">
                <Sparkles size={17} />
              </div>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask me anything... Find services, build apps, get quotes"
                className="flex-1 outline-none text-sm text-foreground placeholder-muted-foreground bg-transparent min-w-0 py-2 font-sans"
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
