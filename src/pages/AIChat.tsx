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
  MessageSquare,
  ExternalLink,
  Paperclip,
  Globe,
  FileText,
  Mail,
} from 'lucide-react';
import { useBlitzStream, CallStatusType } from '../hooks/useBlitzStream';
import { useBuildStream } from '../hooks/useBuildStream';
import { useInboxStream, InboxSummary } from '../hooks/useInboxStream';
import { InboxPreviewCard } from '../components/chat/InboxPreviewCard';
import { Markdown } from '../components/ui/markdown';
import { SourceList } from '../components/ui/source';
import { Steps, StepsTrigger, StepsContent, StepsItem } from '../components/ui/steps';
import { BrowserMockup } from '../components/ui/browser-mockup';
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputBottomBar,
  PromptInputChips,
  PromptInputChip,
  PromptInputActions,
  PromptInputAction,
  PromptInputSubmit,
} from '../components/ui/prompt-input';
import { PromptSuggestion } from '../components/ui/prompt-suggestion';
import { ModelSelectorDropdown, MISTRAL_MODELS } from '../components/ui/model-selector';
import {
  ChatHistory,
  useChatHistory,
  generateSessionTitle,
  getSessionType,
} from '../components/ui/chat-history';
import { cn } from '@/lib/utils';

type MessageRole = 'user' | 'assistant';
type AgentType = 'blitz' | 'build' | 'chat' | 'inbox' | null;

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

interface SourceInfo {
  href: string;
  title: string;
  description?: string;
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
  sources?: SourceInfo[];
  inboxSummary?: InboxSummary;
  inboxAuthUrl?: string | null;
  inboxStatus?: string;
}

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Prompt suggestions for the welcome screen
const PROMPT_SUGGESTIONS = [
  { text: 'Find me a plumber in London', icon: <Phone size={12} /> },
  { text: 'Build a landing page for my startup', icon: <Code size={12} /> },
  { text: 'Get quotes from 3 electricians', icon: <Sparkles size={12} /> },
  { text: 'Check my email', icon: <Mail size={12} /> },
];

export default function AIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [activeBuildSessionId, setActiveBuildSessionId] = useState<string | null>(null);
  const [activeBuildMessageId, setActiveBuildMessageId] = useState<string | null>(null);
  const [activeInboxSessionId, setActiveInboxSessionId] = useState<string | null>(null);
  const [activeInboxMessageId, setActiveInboxMessageId] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState('mixtral-8x7b');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyFilter, setHistoryFilter] = useState<'all' | 'blitz' | 'build'>('all');
  const [activeTab, setActiveTab] = useState<'chat' | 'calls' | 'builds'>('chat');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Chat history hook for localStorage persistence
  const chatHistory = useChatHistory();

  const stream = useBlitzStream(activeSessionId);
  const buildStream = useBuildStream(activeBuildSessionId);
  const inboxStream = useInboxStream(activeInboxSessionId);

  // When selecting a session from history, load its messages
  const handleSelectSession = (sessionId: string) => {
    const session = chatHistory.sessions.find(s => s.id === sessionId);
    if (session) {
      chatHistory.selectSession(sessionId);
      setMessages(session.messages || []);
    }
  };

  // Save messages to current session whenever they change
  useEffect(() => {
    if (chatHistory.currentSessionId && messages.length > 0 && chatHistory.isLoaded) {
      const firstUserMsg = messages.find(m => m.role === 'user');
      const lastMsg = messages[messages.length - 1];
      const sessionType = messages.find(m => m.agent)?.agent || 'chat';

      chatHistory.updateSession(chatHistory.currentSessionId, {
        messages,
        title: firstUserMsg ? generateSessionTitle(firstUserMsg.content) : 'New Chat',
        preview: lastMsg?.content?.substring(0, 60) || '',
        type: sessionType as 'chat' | 'blitz' | 'build',
      });
    }
  }, [messages, chatHistory.currentSessionId, chatHistory.isLoaded]);

  // Start new chat
  const handleNewChat = () => {
    setMessages([]);
    chatHistory.setCurrentSessionId(null);
    setHistoryOpen(false);
  };

  // Sidebar button handlers
  const handleHomeClick = () => {
    handleNewChat();
    setActiveTab('chat');
  };

  const handleChatClick = () => {
    setHistoryOpen(!historyOpen);
    setHistoryFilter('all');
    setActiveTab('chat');
  };

  const handleCallsClick = () => {
    setHistoryOpen(true);
    setHistoryFilter('blitz');
    setActiveTab('calls');
  };

  const handleBuildsClick = () => {
    setHistoryOpen(true);
    setHistoryFilter('build');
    setActiveTab('builds');
  };

  const prevMessagesLengthRef = useRef(0);
  useEffect(() => {
    // Only auto-scroll when a NEW message is added — not on every build/progress update.
    // Prevents being stuck when build stream frequently updates the same message.
    if (messages.length > prevMessagesLengthRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMessagesLengthRef.current = messages.length;
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
          content = buildStream.message || 'Your site is ready!';
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

  // Handle inbox stream updates
  useEffect(() => {
    if (!activeInboxMessageId || !activeInboxSessionId) return;

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== activeInboxMessageId) return msg;
        let content = msg.content;
        if (inboxStream.inboxStatus === 'checking') content = 'Checking your Gmail connection...';
        else if (inboxStream.inboxStatus === 'auth_required') content = 'You need to connect your Gmail account.';
        else if (inboxStream.inboxStatus === 'fetching') content = 'Fetching your emails...';
        else if (inboxStream.inboxStatus === 'summarizing') content = `Summarizing ${inboxStream.emailCount || ''} emails...`;
        else if (inboxStream.inboxStatus === 'complete' && inboxStream.summary) content = inboxStream.message || 'Here\'s your inbox summary:';
        else if (inboxStream.inboxStatus === 'error') content = inboxStream.error || 'Something went wrong checking your inbox.';
        return {
          ...msg,
          content,
          isThinking: false,
          inboxSummary: inboxStream.summary || msg.inboxSummary,
          inboxAuthUrl: inboxStream.authUrl || msg.inboxAuthUrl,
          inboxStatus: inboxStream.inboxStatus || msg.inboxStatus,
        };
      })
    );

    if (inboxStream.inboxStatus === 'complete' || inboxStream.inboxStatus === 'error' || inboxStream.inboxStatus === 'auth_required') {
      setIsLoading(false);
      setActiveInboxSessionId(null);
      setActiveInboxMessageId(null);
    }
  }, [inboxStream, activeInboxMessageId, activeInboxSessionId]);

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

    // Create a new session if we don't have one
    if (!chatHistory.currentSessionId) {
      chatHistory.createSession('chat');
    }

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

      // Get or create entity ID for Composio (session-scoped)
      let entityId = localStorage.getItem('friendly_entity_id');
      if (!entityId) {
        entityId = `inbox-${crypto.randomUUID()}`;
        localStorage.setItem('friendly_entity_id', entityId);
      }

      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageText,
          conversation_history: conversationHistory,
          model: selectedModel,
          web_search: webSearchEnabled,
          entity_id: entityId,
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
            sources: data.sources || undefined,
          }
        )
      );

      if (data.agent === 'blitz' && data.session_id) {
        setActiveSessionId(data.session_id);
        setActiveMessageId(thinkingMessageId);
        // Update session type to blitz
        if (chatHistory.currentSessionId) {
          chatHistory.updateSession(chatHistory.currentSessionId, { type: 'blitz' });
        }
      } else if (data.agent === 'build' && data.session_id) {
        setActiveBuildSessionId(data.session_id);
        setActiveBuildMessageId(thinkingMessageId);
        // Update session type to build
        if (chatHistory.currentSessionId) {
          chatHistory.updateSession(chatHistory.currentSessionId, { type: 'build' });
        }
      } else if (data.agent === 'inbox' && data.session_id) {
        setActiveInboxSessionId(data.session_id);
        setActiveInboxMessageId(thinkingMessageId);
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

  const handleSuggestionClick = (text: string) => {
    setInput(text);
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
          <button
            onClick={handleHomeClick}
            className="p-2.5 hover:bg-muted rounded-xl transition-colors text-muted-foreground hover:text-foreground"
            title="New Chat"
          >
            <Home size={17} />
          </button>
          <button
            onClick={handleChatClick}
            className={`p-2.5 rounded-xl transition-colors ${activeTab === 'chat' && historyOpen ? 'bg-accent text-accent-foreground' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`}
            title="Chat History"
          >
            <MessageSquare size={17} />
          </button>
          <button
            onClick={handleCallsClick}
            className={`p-2.5 rounded-xl transition-colors ${activeTab === 'calls' ? 'bg-accent text-accent-foreground' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`}
            title="Call History"
          >
            <Phone size={17} />
          </button>
          <button
            onClick={handleBuildsClick}
            className={`p-2.5 rounded-xl transition-colors ${activeTab === 'builds' ? 'bg-accent text-accent-foreground' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`}
            title="Build History"
          >
            <Code size={17} />
          </button>
        </div>
        <button className="mt-auto text-muted-foreground hover:text-foreground transition-colors" title="Settings">
          <Settings size={17} />
        </button>
      </aside>

      {/* Chat History Sidebar */}
      <ChatHistory
        sessions={chatHistory.sessions}
        currentSessionId={chatHistory.currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={chatHistory.deleteSession}
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        filter={historyFilter}
        onFilterChange={setHistoryFilter}
      />

      {/* Chat Area */}
      <main className="flex-1 min-h-0 overflow-y-auto flex flex-col relative">
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

              {/* Prompt Suggestions - minimal bubbles */}
              <div className="flex flex-wrap gap-2 justify-center mt-3">
                {PROMPT_SUGGESTIONS.map((suggestion) => (
                  <PromptSuggestion
                    key={suggestion.text}
                    onClick={() => handleSuggestionClick(suggestion.text)}
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <span className="text-muted-foreground/70 opacity-80">{suggestion.icon}</span>
                      {suggestion.text}
                    </span>
                  </PromptSuggestion>
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

                        {/* Markdown rendered content */}
                        <Markdown className="text-foreground">{message.content}</Markdown>

                        {/* Source citations */}
                        {message.sources && message.sources.length > 0 && (
                          <SourceList sources={message.sources} />
                        )}

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
                                  const isLast = idx === message.callStatuses!.length - 1;

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

                        {/* VibeCoder — Apple-style browser mockup (replaces purple template) */}
                        {message.agent === 'build' && (
                          <div className="mt-3">
                            <BrowserMockup url={message.previewUrl || 'https://friendly.dev/preview'} className="rounded-2xl shadow-sm">
                              {/* Build steps inside browser content */}
                              {message.buildSteps && message.buildSteps.length > 0 && (
                                <div className="px-4 pt-3 pb-2 border-b border-border/50">
                                  <Steps
                                    key={`steps-${message.id}-${message.buildSteps.every(s => s.status === 'complete')}`}
                                    defaultOpen={!message.buildSteps.every(s => s.status === 'complete')}
                                  >
                                    <StepsTrigger
                                      leftIcon={
                                        message.buildSteps.every(s => s.status === 'complete')
                                          ? <Check size={14} className="text-green-500" />
                                          : <Loader2 size={14} className="text-muted-foreground animate-spin" />
                                      }
                                    >
                                      {message.buildSteps.every(s => s.status === 'complete')
                                        ? 'Build complete'
                                        : 'Building...'}
                                    </StepsTrigger>
                                    <StepsContent showBar={true}>
                                      {message.buildSteps.map((step) => (
                                        <StepsItem key={step.id} status={step.status}>
                                          {step.label}
                                        </StepsItem>
                                      ))}
                                    </StepsContent>
                                  </Steps>
                                </div>
                              )}
                              {/* App preview iframe */}
                              {message.previewUrl ? (
                                <>
                                  <iframe
                                    src={message.previewUrl}
                                    className={cn(
                                      "w-full bg-white",
                                      message.buildSteps?.every(s => s.status === 'complete')
                                        ? "h-80"
                                        : "h-64"
                                    )}
                                    title="Website Preview"
                                  />
                                  <div className="flex justify-center p-3 border-t border-border/50 bg-muted/20">
                                    <a
                                      href={message.previewUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-foreground font-sans font-medium flex items-center gap-1.5 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors border border-border"
                                    >
                                      <ExternalLink size={12} />
                                      Open Full Preview
                                    </a>
                                  </div>
                                </>
                              ) : (
                                <div className="grid place-content-center h-48 text-muted-foreground text-sm font-sans">
                                  Preparing preview...
                                </div>
                              )}
                            </BrowserMockup>
                          </div>
                        )}

                        {/* Inbox Preview Card */}
                        {message.agent === 'inbox' && (
                          <InboxPreviewCard
                            status={(message.inboxStatus ?? 'checking') as 'checking' | 'auth_required' | 'fetching' | 'summarizing' | 'complete' | 'error'}
                            summary={message.inboxSummary}
                            authUrl={message.inboxAuthUrl}
                            error={message.inboxStatus === 'error' ? message.content : undefined}
                          />
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="h-36 shrink-0" />
        </div>

        {/* Floating Input - Le Chat Style */}
        <div className="sticky bottom-0 bg-gradient-to-t from-background via-background/95 to-transparent pt-6 pb-4 px-8 md:px-20 lg:px-36">
          <div className="max-w-2xl mx-auto space-y-4">
            <PromptInput
              value={input}
              onValueChange={setInput}
              isLoading={isLoading}
              onSubmit={handleSend}
              maxHeight={200}
            >
              <PromptInputTextarea
                placeholder="Ask Friendly or @mention an agent"
              />
              <PromptInputBottomBar>
                <PromptInputChips>
                  <ModelSelectorDropdown
                    models={MISTRAL_MODELS}
                    selectedModel={selectedModel}
                    onModelChange={setSelectedModel}
                  />
                  <PromptInputChip
                    icon={<Globe size={12} />}
                    active={webSearchEnabled}
                    onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                    className="px-2 py-1 text-xs gap-1"
                  >
                    Web search
                  </PromptInputChip>
                </PromptInputChips>
                <PromptInputActions>
                  <PromptInputAction tooltip="Attach file" side="top">
                    <button className="w-8 h-8 flex items-center justify-center hover:bg-muted rounded-lg transition-colors text-muted-foreground hover:text-foreground">
                      <Paperclip size={18} />
                    </button>
                  </PromptInputAction>
                  <PromptInputSubmit
                    icon={<ArrowRight size={18} />}
                    loadingIcon={<Loader2 size={18} className="animate-spin" />}
                  />
                </PromptInputActions>
              </PromptInputBottomBar>
            </PromptInput>

            <p className="text-center text-[11px] text-muted-foreground font-sans">
              Friendly AI can make mistakes. Verify important information.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}