import { Sparkles, Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AgentCard from "@/components/AgentCard";
import FriendlyLogo from "@/components/FriendlyLogo";

const Dashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 bg-background border-b border-border">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center">
            <FriendlyLogo size="md" />
          </a>
          <span className="text-xs font-sans text-muted-foreground">Agent Dashboard</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-10">
        <div className="mb-8">
          <h1 className="font-serif text-4xl text-foreground">Choose an agent</h1>
          <p className="font-sans text-muted-foreground mt-2">
            Pick what you want done. Friendly routes you to the right execution flow.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <AgentCard
            name="Blitz"
            description="Calls multiple businesses in parallel and returns live quote comparisons in chat."
            status="active"
            icon={Zap}
            ctaLabel="Open Blitz"
            onClick={() => navigate("/chat")}
          />
          <AgentCard
            name="VibeCoder"
            description="Builds apps from natural-language prompts with your existing vibecoding workspace."
            status="active"
            icon={Sparkles}
            ctaLabel="Open VibeCoder"
            onClick={() => navigate("/vibecoder")}
          />
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
