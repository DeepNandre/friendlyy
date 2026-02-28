import React, { useState, useRef, useEffect } from 'react';
import {
  Home,
  Sparkles,
  Phone,
  Code,
  Settings,
  Lock,
  Plus,
  RefreshCcw,
  Globe,
  ArrowRight,
  Check,
  X,
  Clock,
  Loader2,
  ChevronRight,
  Zap,
  MessageSquare,
  MoreHorizontal
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

  // SSE stream hook for Blitz
  const stream = useBlitzStream(activeSessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Update message with SSE data
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
        if (stream.sessionStatus === 'searching') {
          content = 'Searching for businesses near you...';
        } else if (stream.sessionStatus === 'calling') {
          content = `Found ${stream.callStatuses.length} businesses. Making calls now...`;
        } else if (stream.sessionStatus === 'complete' && stream.summary) {
          content = stream.summary;
        } else if (stream.sessionStatus === 'error') {
          content = stream.error || 'Something went wrong. Please try again.';
        }

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

  const mapCallStatus = (status: CallStatusType): CallStatus['status'] => {
    switch (status) {
      case 'pending': return 'pending';
      case 'ringing': return 'ringing';
      case 'connected':
      case 'speaking':
      case 'recording': return 'connected';
      case 'complete': return 'complete';
      case 'no_answer': return 'no_answer';
      case 'busy': return 'busy';
      case 'failed': return 'failed';
      default: return 'pending';
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input.trim();
    setInput('');
    setIsLoading(true);

    // Add thinking message
    const thinkingMessageId = (Date.now() + 1).toString();
    const thinkingMessage: Message = {
      id: thinkingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isThinking: true,
    };
    setMessages((prev) => [...prev, thinkingMessage]);

    try {
      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
      });

      if (!response.ok) throw new Error('Failed to send message');

      const data = await response.json();

      // Update the thinking message with real content
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== thinkingMessageId) return msg;
          return {
            ...msg,
            content: data.message,
            agent: data.agent as AgentType,
            sessionId: data.session_id,
            isThinking: false,
            thinkingTime: 2,
            callStatuses: data.agent === 'blitz' ? [] : undefined,
          };
        })
      );

      if (data.agent === 'blitz' && data.session_id) {
        setActiveSessionId(data.session_id);
        setActiveMessageId(thinkingMessageId);
      } else {
        setIsLoading(false);
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== thinkingMessageId) return msg;
          return {
            ...msg,
            content: "Sorry, I couldn't process that. Please try again.",
            isThinking: false,
          };
        })
      );
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: CallStatus['status']) => {
    switch (status) {
      case 'pending':
        return <Clock size={14} className="text-gray-400" />;
      case 'ringing':
        return <Phone size={14} className="text-amber-500 animate-pulse" />;
      case 'connected':
        return <Loader2 size={14} className="text-blue-500 animate-spin" />;
      case 'complete':
        return <Check size={14} className="text-emerald-500" />;
      case 'failed':
      case 'no_answer':
      case 'busy':
        return <X size={14} className="text-red-400" />;
      default:
        return <Clock size={14} className="text-gray-400" />;
    }
  };

  const getStatusText = (status: CallStatus['status']) => {
    switch (status) {
      case 'pending': return 'Waiting...';
      case 'ringing': return 'Ringing...';
      case 'connected': return 'On call...';
      case 'complete': return 'Done';
      case 'failed': return 'Failed';
      case 'no_answer': return 'No answer';
      case 'busy': return 'Busy';
      default: return '';
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] p-4 md:p-6 font-sans text-gray-800 flex flex-col items-center">

      {/* Top Floating Tags */}
      <div className="w-full max-w-6xl flex justify-between items-center mb-4">
        <div className="flex gap-2">
          <span className="bg-white/80 backdrop-blur-sm px-3 py-1 rounded-full text-[10px] font-semibold text-gray-500 shadow-sm border border-white/50 uppercase tracking-wide">AI Assistant</span>
          <span className="bg-purple-50 backdrop-blur-sm px-3 py-1 rounded-full text-[10px] font-semibold text-purple-600 shadow-sm border border-purple-100 uppercase tracking-wide">Blitz Agent</span>
        </div>
        <div className="flex gap-2">
          <span className="bg-blue-50 backdrop-blur-sm px-3 py-1 rounded-full text-[10px] font-semibold text-blue-600 shadow-sm border border-blue-100 uppercase tracking-wide">VibeCoder</span>
        </div>
      </div>

      {/* Main App Window */}
      <div className="w-full max-w-6xl bg-white rounded-3xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] overflow-hidden flex flex-col h-[calc(100vh-120px)] min-h-[600px] relative border border-gray-200/60">

        {/* Header / Browser Bar */}
        <header className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50/50">
          {/* macOS Dots */}
          <div className="flex gap-1.5 w-24">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56] border border-[#e0443e]"></div>
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-[#dea123]"></div>
            <div className="w-3 h-3 rounded-full bg-[#27c93f] border border-[#1aab29]"></div>
          </div>

          {/* URL Bar */}
          <div className="flex items-center gap-2 bg-white px-4 py-1.5 rounded-lg text-sm text-gray-600 font-medium flex-1 max-w-md justify-center border border-gray-200">
            <Lock size={12} className="text-gray-400" />
            <span className="text-gray-500">friendly.ai</span>
          </div>

          {/* Right Icons */}
          <div className="flex items-center gap-3 w-24 justify-end text-gray-400">
            <button className="hover:text-gray-600 transition-colors">
              <RefreshCcw size={16} />
            </button>
            <button className="hover:text-gray-600 transition-colors">
              <Plus size={18} />
            </button>
          </div>
        </header>

        {/* Main Body Layout */}
        <div className="flex flex-1 overflow-hidden relative">

          {/* Left Sidebar */}
          <aside className="w-14 border-r border-gray-100 flex flex-col items-center py-4 gap-6 bg-gray-50/30">
            {/* Logo */}
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-purple-500/20">
              <Zap size={16} />
            </div>

            {/* Nav Icons */}
            <div className="flex flex-col gap-2 mt-2">
              <button className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors text-gray-400 hover:text-gray-600">
                <Home size={18} />
              </button>
              <button className="p-2.5 bg-purple-100 text-purple-600 rounded-xl transition-colors">
                <MessageSquare size={18} />
              </button>
              <button className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors text-gray-400 hover:text-gray-600">
                <Phone size={18} />
              </button>
              <button className="p-2.5 hover:bg-gray-100 rounded-xl transition-colors text-gray-400 hover:text-gray-600">
                <Code size={18} />
              </button>
            </div>

            <button className="mt-auto text-gray-300 hover:text-gray-500 transition-colors">
              <Settings size={18} />
            </button>
          </aside>

          {/* Chat Feed */}
          <main className="flex-1 overflow-y-auto px-6 md:px-12 lg:px-20 py-8 flex flex-col">

            {/* Welcome State */}
            {messages.length === 0 && (
              <div className="flex-1 flex flex-col items-center justify-center text-center max-w-xl mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center text-white shadow-xl shadow-purple-500/20 mb-6">
                  <Sparkles size={28} />
                </div>
                <h1 className="text-2xl font-semibold text-gray-900 mb-2">Hey, I'm Friendly</h1>
                <p className="text-gray-500 mb-8">
                  I can help you find services, make calls, and build apps. What do you need?
                </p>

                {/* Quick Actions */}
                <div className="flex flex-wrap gap-2 justify-center">
                  <button
                    onClick={() => setInput('Find me a plumber who can come tomorrow')}
                    className="bg-gray-100 hover:bg-gray-200 px-4 py-2 rounded-full text-sm text-gray-700 transition-colors flex items-center gap-2"
                  >
                    <Phone size={14} />
                    Find a plumber
                  </button>
                  <button
                    onClick={() => setInput('Build me a landing page for my startup')}
                    className="bg-gray-100 hover:bg-gray-200 px-4 py-2 rounded-full text-sm text-gray-700 transition-colors flex items-center gap-2"
                  >
                    <Code size={14} />
                    Build a landing page
                  </button>
                  <button
                    onClick={() => setInput('Get quotes from 3 electricians in London')}
                    className="bg-gray-100 hover:bg-gray-200 px-4 py-2 rounded-full text-sm text-gray-700 transition-colors flex items-center gap-2"
                  >
                    <Zap size={14} />
                    Get electrician quotes
                  </button>
                </div>
              </div>
            )}

            {/* Messages */}
            <div className="flex flex-col gap-6 max-w-3xl w-full mx-auto">
              {messages.map((message) => (
                <div key={message.id} className="flex flex-col gap-3">

                  {/* User Message */}
                  {message.role === 'user' && (
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-sm font-medium shrink-0">
                        U
                      </div>
                      <div className="flex-1">
                        <p className="text-[15px] text-gray-900 leading-relaxed">
                          {message.content}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Assistant Message */}
                  {message.role === 'assistant' && (
                    <div className="flex flex-col gap-3 pl-11">
                      {/* Thinking indicator */}
                      {message.isThinking && (
                        <div className="flex items-center gap-2 text-gray-400 text-sm">
                          <div className="flex gap-1">
                            <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                            <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                            <div className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                          </div>
                          <span>Thinking...</span>
                        </div>
                      )}

                      {/* Response */}
                      {!message.isThinking && (
                        <>
                          {message.thinkingTime && (
                            <div className="text-gray-400 text-xs font-medium flex items-center gap-1.5">
                              <Sparkles size={12} />
                              Thought for {message.thinkingTime}s
                            </div>
                          )}

                          <p className="text-[15px] text-gray-900 leading-relaxed">
                            {message.content}
                          </p>

                          {/* Blitz Call Widget */}
                          {message.agent === 'blitz' && message.callStatuses && message.callStatuses.length > 0 && (
                            <div className="border border-gray-200 rounded-2xl bg-white shadow-sm overflow-hidden mt-2">
                              {/* Widget Header */}
                              <div className="flex justify-between items-center px-4 py-3 bg-gradient-to-r from-purple-50 to-blue-50 border-b border-gray-100">
                                <div className="flex items-center gap-2">
                                  <div className="bg-purple-500 text-white p-1.5 rounded-lg">
                                    <Phone size={14} />
                                  </div>
                                  <span className="font-semibold text-gray-700 text-sm">Blitz Calls</span>
                                </div>
                                <span className="text-xs text-gray-400">
                                  {message.callStatuses.filter(c => c.status === 'complete').length}/{message.callStatuses.length} complete
                                </span>
                              </div>

                              {/* Call List */}
                              <div className="divide-y divide-gray-50">
                                {message.callStatuses.map((call, idx) => (
                                  <div key={idx} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
                                    <div className="flex items-center gap-3">
                                      {getStatusIcon(call.status)}
                                      <div>
                                        <p className="text-sm font-medium text-gray-900">{call.business}</p>
                                        {call.phone && (
                                          <p className="text-xs text-gray-400">{call.phone}</p>
                                        )}
                                      </div>
                                    </div>
                                    <div className="text-right">
                                      {call.result ? (
                                        <p className="text-sm text-emerald-600 font-medium">{call.result}</p>
                                      ) : call.error ? (
                                        <p className="text-sm text-red-400">{call.error}</p>
                                      ) : (
                                        <p className="text-xs text-gray-400">{getStatusText(call.status)}</p>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* VibeCoder Widget */}
                          {message.agent === 'vibecoder' && (
                            <div className="border border-gray-200 rounded-2xl bg-white shadow-sm overflow-hidden mt-2">
                              <div className="flex justify-between items-center px-4 py-3 bg-gradient-to-r from-blue-50 to-cyan-50 border-b border-gray-100">
                                <div className="flex items-center gap-2">
                                  <div className="bg-blue-500 text-white p-1.5 rounded-lg">
                                    <Code size={14} />
                                  </div>
                                  <span className="font-semibold text-gray-700 text-sm">VibeCoder</span>
                                </div>
                                <button className="text-xs text-blue-500 hover:text-blue-600 font-medium flex items-center gap-1">
                                  Open Editor <ChevronRight size={14} />
                                </button>
                              </div>
                              <div className="p-4 text-sm text-gray-600">
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

            {/* Bottom spacer */}
            <div className="h-24 shrink-0"></div>
          </main>

          {/* Floating Bottom Input Bar */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-2xl px-4 z-20">
            <div className="bg-white rounded-2xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.12)] border border-gray-200 flex items-center p-2 gap-3">
              <div className="pl-2">
                <Sparkles size={18} className="text-purple-500" />
              </div>

              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask me anything... Find services, build apps, get quotes"
                className="flex-1 outline-none text-sm text-gray-700 placeholder-gray-400 bg-transparent min-w-0 py-2"
                disabled={isLoading}
              />

              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="bg-purple-500 hover:bg-purple-600 disabled:bg-gray-200 disabled:cursor-not-allowed text-white rounded-xl w-10 h-10 flex items-center justify-center shrink-0 transition-colors"
              >
                {isLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <ArrowRight size={18} />
                )}
              </button>
            </div>

            <p className="text-center text-[11px] text-gray-400 mt-2">
              Friendly AI can make mistakes. Verify important information.
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
