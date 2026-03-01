import { Phone, Code, Clock } from 'lucide-react';

interface WelcomeStateProps {
  onSendMessage: (text: string) => void;
}

const QUICK_ACTIONS = [
  { icon: <Phone size={13} />, label: 'Find a plumber', value: 'Find me a plumber who can come tomorrow' },
  { icon: <Code size={13} />, label: 'Build a website', value: 'Build me a landing page for my startup' },
  { icon: <Clock size={13} />, label: 'Wait on hold for me', value: 'Wait on hold with HMRC for me' },
];

export default function WelcomeState({ onSendMessage }: WelcomeStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center max-w-lg mx-auto gap-6 min-h-[60vh]">
      <div className="w-20 h-20 rounded-[22px] bg-background flex items-center justify-center p-2 shadow-2xl shadow-foreground/20 border border-border overflow-hidden">
        <img src="/friendly-logo-monochrome.jpg" alt="Friendly" className="w-full h-full object-contain" />
      </div>
      <div>
        <h1 className="text-3xl sm:text-4xl font-serif text-foreground mb-3">Hey, I'm Friendly</h1>
        <p className="text-base text-muted-foreground font-sans leading-relaxed">
          I can help you find services, make calls, and build apps. What do you need?
        </p>
      </div>
      <div className="flex flex-wrap gap-2.5 justify-center mt-2">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => onSendMessage(action.value)}
            className="bg-card hover:bg-muted border border-border px-4 py-2.5 rounded-full text-sm text-foreground font-sans font-medium transition-all hover:shadow-sm flex items-center gap-2"
          >
            <span className="text-muted-foreground">{action.icon}</span>
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
