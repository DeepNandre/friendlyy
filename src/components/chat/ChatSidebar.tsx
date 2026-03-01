import { Home, Phone, Code, Settings, MessageSquare } from 'lucide-react';

export default function ChatSidebar() {
  return (
    <aside className="hidden md:flex w-16 border-r border-border flex-col items-center py-6 gap-5 bg-background shrink-0">
      <div className="w-9 h-9 rounded-2xl bg-background flex items-center justify-center p-1.5 shadow-lg border border-border overflow-hidden">
        <img src="/friendly-logo-monochrome.jpg" alt="Friendly" className="w-full h-full object-contain" />
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
  );
}
