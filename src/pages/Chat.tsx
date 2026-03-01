import { useState, useRef, useEffect } from "react";
import { Send, Phone, Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { useBlitzStream, CallStatusType } from "../hooks/useBlitzStream";

type MessageStatus = "sending" | "sent" | "error";
type AgentStatus = "idle" | "calling" | "ringing" | "connected" | "complete" | "failed" | "no_answer" | "busy";

interface CallStatus {
  business: string;
  status: AgentStatus;
  result?: string;
  error?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  status?: MessageStatus;
  callStatuses?: CallStatus[];
  sessionId?: string;
}

const BLITZ_API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE || import.meta.env.VITE_API_URL || "http://localhost:8000";

const assertNever = (value: never): never => {
  throw new Error(`Unhandled value: ${String(value)}`);
};

const Chat = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hey! I'm Friendly. Tell me what you need — I'll make the calls, get the quotes, and handle the boring stuff. What can I help you with?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // SSE stream hook
  const stream = useBlitzStream(activeSessionId);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Update message with SSE data
  useEffect(() => {
    if (!activeMessageId || !activeSessionId) return;

    // Map stream call statuses to message format
    const mappedStatuses: CallStatus[] = stream.callStatuses.map((cs) => ({
      business: cs.business,
      status: mapCallStatus(cs.status),
      result: cs.result,
      error: cs.error,
    }));

    // Update the active message with new call statuses
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== activeMessageId) return msg;

        // Update content based on session status
        let content = msg.content;
        if (stream.sessionStatus === "searching") {
          content = "Searching for businesses near you...";
        } else if (stream.sessionStatus === "calling") {
          content = `Calling ${stream.callStatuses.length} businesses...`;
        } else if (stream.sessionStatus === "complete" && stream.summary) {
          content = stream.summary;
        } else if (stream.sessionStatus === "error") {
          content = stream.error || "Something went wrong. Please try again.";
        }

        return {
          ...msg,
          content,
          callStatuses: mappedStatuses.length > 0 ? mappedStatuses : msg.callStatuses,
        };
      })
    );

    // Clear loading when complete
    if (stream.sessionStatus === "complete" || stream.sessionStatus === "error") {
      setIsLoading(false);
      setActiveSessionId(null);
      setActiveMessageId(null);
    }
  }, [stream, activeMessageId, activeSessionId]);

  const mapCallStatus = (status: CallStatusType): AgentStatus => {
    switch (status) {
      case "pending":
        return "idle";
      case "ringing":
        return "ringing";
      case "connected":
      case "speaking":
      case "recording":
        return "connected";
      case "complete":
        return "complete";
      case "no_answer":
        return "no_answer";
      case "busy":
        return "busy";
      case "failed":
        return "failed";
      default:
        return assertNever(status);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
      status: "sent",
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input.trim();
    setInput("");
    setIsLoading(true);

    try {
      // Call the backend API
      const response = await fetch(`${BLITZ_API_BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageText,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to send message");
      }

      const data = await response.json();

      // Create assistant message
      const assistantMessageId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: "assistant",
        content: data.message,
        timestamp: new Date(),
        sessionId: data.session_id,
        callStatuses: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If this is a blitz request with a session ID, start listening to SSE
      if (data.agent === "blitz" && data.session_id) {
        setActiveSessionId(data.session_id);
        setActiveMessageId(assistantMessageId);
      } else {
        // For non-blitz responses, we're done
        setIsLoading(false);
      }
    } catch (error) {
      console.error("Error sending message:", error);

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I couldn't process that. Please try again.",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status: AgentStatus) => {
    switch (status) {
      case "ringing":
        return <Phone className="w-4 h-4 text-yellow-500 animate-pulse" />;
      case "calling":
        return <Phone className="w-4 h-4 text-yellow-500 animate-pulse" />;
      case "connected":
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case "complete":
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case "failed":
      case "no_answer":
      case "busy":
        return <XCircle className="w-4 h-4 text-red-400" />;
      case "idle":
        return <Clock className="w-4 h-4 text-muted-foreground" />;
      default:
        return assertNever(status);
    }
  };

  const getStatusText = (status: AgentStatus) => {
    switch (status) {
      case "ringing":
        return "Ringing...";
      case "calling":
        return "Calling...";
      case "connected":
        return "Connected, asking...";
      case "complete":
        return "";
      case "failed":
        return "";
      case "no_answer":
        return "";
      case "busy":
        return "";
      case "idle":
        return "Waiting";
      default:
        return assertNever(status);
    }
  };

  const getResultText = (call: CallStatus) => {
    if (call.result) return call.result;
    if (call.error) return call.error;
    if (call.status === "no_answer") return "No answer";
    if (call.status === "busy") return "Line busy";
    if (call.status === "failed") return "Call failed";
    return undefined;
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background border-b border-border">
        <div className="max-w-3xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[hsl(220,70%,55%)] flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 2a10 10 0 0 1 0 20"/>
                <path d="M2 12h20"/>
              </svg>
            </div>
            <span className="font-serif text-xl font-normal text-foreground">Friendly</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="/dashboard" className="text-xs font-sans text-muted-foreground hover:text-foreground transition-colors">
              Dashboard
            </a>
            <span className="text-xs font-sans text-muted-foreground">Powered by Mistral AI</span>
          </div>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  message.role === "user"
                    ? "bg-foreground text-background"
                    : "bg-muted text-foreground"
                }`}
              >
                <p className="font-sans text-sm whitespace-pre-wrap">{message.content}</p>

                {/* Call statuses */}
                {message.callStatuses && message.callStatuses.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {message.callStatuses.map((call, idx) => (
                      <div
                        key={idx}
                        className={`flex items-start gap-3 p-3 rounded-xl ${
                          message.role === "user" ? "bg-background/10" : "bg-background"
                        }`}
                      >
                        {getStatusIcon(call.status)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-sans text-sm font-medium truncate">
                              {call.business}
                            </span>
                            {!["complete", "failed", "no_answer", "busy"].includes(call.status) && (
                              <span className="text-xs text-muted-foreground">
                                {getStatusText(call.status)}
                              </span>
                            )}
                          </div>
                          {getResultText(call) && (
                            <p className={`text-xs mt-1 ${
                              ["failed", "no_answer", "busy"].includes(call.status)
                                ? "text-red-400"
                                : "text-muted-foreground"
                            }`}>
                              {getResultText(call)}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-xs opacity-50 mt-2">
                  {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input */}
      <footer className="sticky bottom-0 bg-background border-t border-border">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Find me a plumber who can come tomorrow..."
              className="flex-1 bg-muted rounded-full px-5 py-3 font-sans text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-foreground/20"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="w-12 h-12 rounded-full bg-foreground text-background flex items-center justify-center hover:opacity-80 transition-opacity disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-center text-xs text-muted-foreground mt-3">
            Friendly makes real phone calls on your behalf. Built at Mistral Hackathon 2026.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Chat;
