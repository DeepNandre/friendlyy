import { Code, ChevronRight, RefreshCw, Pencil } from 'lucide-react';
import { Skeleton } from '../ui/skeleton';

const VIBECODER_URL = import.meta.env.VITE_VIBECODER_URL || 'http://localhost:3000';

interface VibeCoderWidgetProps {
  status?: 'idle' | 'building' | 'complete';
}

export default function VibeCoderWidget({ status = 'idle' }: VibeCoderWidgetProps) {
  return (
    <div className="border border-border rounded-2xl bg-card overflow-hidden mt-1 shadow-sm">
      <div className="flex justify-between items-center px-4 py-3 bg-accent/20 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="bg-foreground text-background p-1.5 rounded-lg">
            <Code size={13} />
          </div>
          <span className="font-semibold text-foreground text-sm font-sans">VibeCoder</span>
        </div>
        <a
          href="/vibecoder"
          className="text-xs text-foreground font-medium font-sans flex items-center gap-1 hover:opacity-70 transition-opacity"
        >
          Open Editor <ChevronRight size={13} />
        </a>
      </div>

      {/* Preview area */}
      <div className="p-4">
        {status === 'building' ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-5/6" />
            <p className="text-xs text-muted-foreground font-sans mt-3">Building your project...</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground font-sans">
            Ready to build your project. Click to open the VibeCoder editor.
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 pb-3">
        <button
          disabled
          className="text-xs text-muted-foreground font-sans font-medium flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border opacity-50 cursor-not-allowed"
        >
          <RefreshCw size={11} />
          Regenerate
        </button>
        <button
          disabled
          className="text-xs text-muted-foreground font-sans font-medium flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border opacity-50 cursor-not-allowed"
        >
          <Pencil size={11} />
          Edit
        </button>
      </div>
    </div>
  );
}
