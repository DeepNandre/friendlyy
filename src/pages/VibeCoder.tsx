import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

const defaultVibeCoderUrl = "http://localhost:3000";

const VibeCoder = () => {
  const vibeCoderUrl = import.meta.env.VITE_VIBECODER_URL || defaultVibeCoderUrl;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-50 bg-background border-b border-border">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-[hsl(220,70%,55%)] flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a10 10 0 0 1 0 20" />
                <path d="M2 12h20" />
              </svg>
            </div>
            <span className="font-serif text-xl font-normal text-foreground">Friendly</span>
          </a>
          <Button asChild variant="outline" className="rounded-full">
            <a href={vibeCoderUrl} target="_blank" rel="noreferrer">
              Open in new tab
              <ExternalLink className="w-4 h-4" />
            </a>
          </Button>
        </div>
      </header>

      <main className="flex-1 p-4">
        <div className="h-full rounded-2xl border border-border overflow-hidden bg-card">
          <iframe
            title="VibeCoder"
            src={vibeCoderUrl}
            className="w-full h-full min-h-[75vh]"
            loading="lazy"
          />
        </div>
      </main>
    </div>
  );
};

export default VibeCoder;
