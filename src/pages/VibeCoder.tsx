import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import FriendlyLogo from "@/components/FriendlyLogo";

const defaultVibeCoderUrl = "http://localhost:3000";

const VibeCoder = () => {
  const vibeCoderUrl = import.meta.env.VITE_VIBECODER_URL || defaultVibeCoderUrl;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="sticky top-0 z-50 bg-background border-b border-border">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/dashboard" className="flex items-center">
            <FriendlyLogo size="md" />
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
