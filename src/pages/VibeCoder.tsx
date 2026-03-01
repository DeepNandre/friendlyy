import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { ExternalLink, ArrowLeft, Code, MessageSquare, Loader2 } from "lucide-react";

const API_BASE =
  import.meta.env.VITE_BLITZ_API_BASE ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000";

const VIBECODER_URL =
  import.meta.env.VITE_VIBECODER_URL || "http://localhost:3000";

const VibeCoder = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const previewId = searchParams.get("preview");

  // Check if the full VibeCoder app is running
  const [vibeCoderAvailable, setVibeCoderAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    // If there's a preview ID, skip the VibeCoder app check — show the preview
    if (previewId) {
      setVibeCoderAvailable(false);
      return;
    }

    // Probe the VibeCoder app to see if it's running
    const controller = new AbortController();
    fetch(VIBECODER_URL, { mode: "no-cors", signal: controller.signal })
      .then(() => setVibeCoderAvailable(true))
      .catch(() => setVibeCoderAvailable(false));

    return () => controller.abort();
  }, [previewId]);

  const previewUrl = previewId
    ? `${API_BASE}/api/build/preview/${previewId}`
    : null;

  // Still checking if VibeCoder app is available
  if (vibeCoderAvailable === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 size={24} className="text-muted-foreground animate-spin" />
      </div>
    );
  }

  // Full VibeCoder app is running — embed it
  if (vibeCoderAvailable && !previewId) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <header className="sticky top-0 z-50 bg-background border-b border-border">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate("/ai")}
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors font-sans"
              >
                <ArrowLeft size={14} />
                Back to chat
              </button>
              <div className="w-px h-5 bg-border" />
              <div className="flex items-center gap-2">
                <div className="bg-foreground text-background p-1.5 rounded-lg">
                  <Code size={13} />
                </div>
                <span className="font-serif text-lg font-normal text-foreground">
                  VibeCoder
                </span>
              </div>
            </div>
            <a
              href={VIBECODER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-full text-sm font-sans text-foreground hover:bg-muted transition-colors"
            >
              Open in new tab
              <ExternalLink size={13} />
            </a>
          </div>
        </header>
        <main className="flex-1 p-4">
          <div className="h-full rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <iframe
              title="VibeCoder App"
              src={VIBECODER_URL}
              className="w-full h-full min-h-[80vh]"
              loading="lazy"
            />
          </div>
        </main>
      </div>
    );
  }

  // Preview mode or VibeCoder not running — show build preview
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-50 bg-background border-b border-border">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/ai")}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors font-sans"
            >
              <ArrowLeft size={14} />
              Back to chat
            </button>
            <div className="w-px h-5 bg-border" />
            <div className="flex items-center gap-2">
              <div className="bg-foreground text-background p-1.5 rounded-lg">
                <Code size={13} />
              </div>
              <span className="font-serif text-lg font-normal text-foreground">
                VibeCoder
              </span>
            </div>
          </div>
          {previewUrl && (
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-full text-sm font-sans text-foreground hover:bg-muted transition-colors"
            >
              Open in new tab
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      </header>

      <main className="flex-1 p-4">
        {previewUrl ? (
          <div className="h-full rounded-2xl border border-border overflow-hidden bg-card shadow-sm">
            <iframe
              title="VibeCoder Preview"
              src={previewUrl}
              className="w-full h-full min-h-[80vh]"
              sandbox="allow-same-origin"
              loading="lazy"
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center min-h-[70vh] gap-4">
            <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center">
              <Code size={28} className="text-muted-foreground" />
            </div>
            <div>
              <h2 className="text-xl font-serif text-foreground mb-2">
                No preview to show
              </h2>
              <p className="text-sm text-muted-foreground font-sans max-w-md">
                Ask Friendly to build you a website in the chat, and your
                preview will appear here.
              </p>
            </div>
            <button
              onClick={() => navigate("/ai")}
              className="inline-flex items-center gap-2 px-4 py-2 bg-foreground text-background rounded-xl text-sm font-medium font-sans hover:opacity-80 transition-opacity mt-2"
            >
              <MessageSquare size={13} />
              Go to Chat
            </button>
          </div>
        )}
      </main>
    </div>
  );
};

export default VibeCoder;
