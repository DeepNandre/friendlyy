import { cn } from "@/lib/utils";

interface BrowserMockupProps {
  /** URL shown in the address bar */
  url?: string;
  /** Content to render inside the browser (e.g. iframe, div) */
  children: React.ReactNode;
  className?: string;
}

/**
 * Browser mockup component — shows content in a browser window frame.
 * Inspired by DaisyUI mockup-browser: toolbar with address bar + content area.
 */
export function BrowserMockup({ url = "https://preview.app", children, className }: BrowserMockupProps) {
  return (
    <div
      className={cn(
        "rounded-lg overflow-hidden border border-border w-full bg-card",
        className
      )}
    >
      {/* Toolbar — traffic lights + address bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="size-2.5 rounded-full bg-red-400/80" />
          <span className="size-2.5 rounded-full bg-amber-400/80" />
          <span className="size-2.5 rounded-full bg-emerald-400/80" />
        </div>
        <div className="flex-1 min-w-0 flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/80 border border-border text-xs text-muted-foreground overflow-hidden">
          <svg
            className="size-3.5 shrink-0 opacity-60"
            fill="currentColor"
            viewBox="0 0 16 16"
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z"
              clipRule="evenodd"
            />
          </svg>
          <span className="truncate font-mono">{url}</span>
        </div>
      </div>
      {/* Content area */}
      <div className="border-t border-border overflow-hidden bg-white min-h-[12rem]">
        {children}
      </div>
    </div>
  );
}
