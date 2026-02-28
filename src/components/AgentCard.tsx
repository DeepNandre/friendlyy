import { ArrowRight, LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

type AgentStatus = "active" | "coming_soon";

interface AgentCardProps {
  name: string;
  description: string;
  status: AgentStatus;
  icon: LucideIcon;
  ctaLabel: string;
  onClick: () => void;
}

const statusLabel: Record<AgentStatus, string> = {
  active: "Active",
  coming_soon: "Coming Soon",
};

const AgentCard = ({ name, description, status, icon: Icon, ctaLabel, onClick }: AgentCardProps) => {
  const isActive = status === "active";

  return (
    <Card className="h-full rounded-2xl border-border bg-card/70">
      <CardHeader className="space-y-4 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="w-11 h-11 rounded-xl bg-[hsl(220,70%,55%)]/10 border border-[hsl(220,70%,55%)]/30 flex items-center justify-center">
            <Icon className="w-5 h-5 text-[hsl(220,70%,55%)]" />
          </div>
          <Badge variant={isActive ? "default" : "secondary"}>{statusLabel[status]}</Badge>
        </div>
        <CardTitle className="font-serif text-2xl">{name}</CardTitle>
      </CardHeader>
      <CardContent className="pb-6">
        <p className="font-sans text-sm text-muted-foreground leading-relaxed">{description}</p>
      </CardContent>
      <CardFooter>
        <Button
          onClick={onClick}
          disabled={!isActive}
          className="w-full rounded-full font-semibold"
          variant={isActive ? "default" : "secondary"}
        >
          {ctaLabel}
          {isActive ? <ArrowRight className="w-4 h-4" /> : null}
        </Button>
      </CardFooter>
    </Card>
  );
};

export default AgentCard;
