import { Phone, Clock, Check, X, Loader2, ExternalLink } from 'lucide-react';
import type { CallStatus } from '../../types/chat';

interface BlitzCallWidgetProps {
  callStatuses: CallStatus[];
  sessionComplete: boolean;
  onViewDetails?: () => void;
}

function getStatusIcon(status: CallStatus['status']) {
  switch (status) {
    case 'pending':
      return <Clock size={13} className="text-muted-foreground" />;
    case 'ringing':
      return <Phone size={13} className="text-amber-500 animate-pulse" />;
    case 'connected':
      return <Loader2 size={13} className="text-foreground animate-spin" />;
    case 'complete':
      return <Check size={13} className="text-emerald-600" />;
    case 'failed':
    case 'no_answer':
    case 'busy':
      return <X size={13} className="text-muted-foreground" />;
    default:
      return <Clock size={13} className="text-muted-foreground" />;
  }
}

function getStatusText(status: CallStatus['status']): string {
  const map: Record<CallStatus['status'], string> = {
    pending: 'Waiting...',
    ringing: 'Ringing...',
    connected: 'On call...',
    complete: 'Done',
    failed: 'Failed',
    no_answer: 'No answer',
    busy: 'Busy',
  };
  return map[status] || '';
}

function getRowClassName(status: CallStatus['status'], isFirst: boolean, isBestOption: boolean): string {
  const base = 'flex items-start sm:items-center justify-between px-4 py-3 transition-colors animate-fade-in-up';

  if (isBestOption) {
    return `${base} ring-2 ring-inset ring-accent/50 bg-accent/5`;
  }
  if (status === 'ringing') {
    return `${base} bg-amber-50/50`;
  }
  if (status === 'complete') {
    return `${base} animate-green-flash`;
  }
  return `${base} hover:bg-muted/50`;
}

export default function BlitzCallWidget({ callStatuses, sessionComplete, onViewDetails }: BlitzCallWidgetProps) {
  const completedCount = callStatuses.filter((c) => c.status === 'complete').length;
  const firstCompleteIndex = callStatuses.findIndex((c) => c.status === 'complete');

  return (
    <div className="border border-border rounded-2xl bg-card overflow-hidden mt-1 shadow-sm">
      {/* Header */}
      <div className="flex justify-between items-center px-4 py-3 bg-accent/30 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="bg-foreground text-background p-1.5 rounded-lg">
            <Phone size={13} />
          </div>
          <span className="font-semibold text-foreground text-sm font-sans">Blitz Calls</span>
        </div>
        <span className="text-xs text-muted-foreground font-sans">
          {completedCount}/{callStatuses.length} complete
        </span>
      </div>

      {/* Call Rows */}
      <div className="divide-y divide-border">
        {callStatuses.map((call, idx) => {
          const isBestOption = sessionComplete && idx === firstCompleteIndex && completedCount > 0;

          return (
            <div
              key={call.phone || call.business}
              className={getRowClassName(call.status, idx === 0, isBestOption)}
              style={{ animationDelay: `${idx * 150}ms` }}
            >
              <div className="flex items-start sm:items-center gap-3 min-w-0 flex-1">
                <div className="mt-0.5 sm:mt-0 shrink-0">
                  {getStatusIcon(call.status)}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-foreground font-sans truncate">{call.business}</p>
                    {isBestOption && (
                      <span className="text-[10px] font-semibold text-accent-foreground bg-accent px-1.5 py-0.5 rounded-full shrink-0">
                        Best option
                      </span>
                    )}
                  </div>
                  {call.phone && (
                    <p className="text-xs text-muted-foreground font-sans">{call.phone}</p>
                  )}
                  {call.address && (
                    <p className="text-xs text-muted-foreground font-sans truncate">{call.address}</p>
                  )}
                </div>
              </div>

              <div className="text-right shrink-0 ml-3 flex flex-col items-end gap-1.5">
                {call.result ? (
                  <>
                    <p className="text-sm text-foreground font-medium font-sans">{call.result}</p>
                    {sessionComplete && call.phone && (
                      <div className="flex items-center gap-2">
                        <a
                          href={`tel:${call.phone}`}
                          className="text-xs text-foreground font-medium font-sans flex items-center gap-1 hover:opacity-70 transition-opacity px-2 py-1 rounded-full border border-border"
                        >
                          <Phone size={10} />
                          Call them
                        </a>
                        {onViewDetails && (
                          <button
                            onClick={onViewDetails}
                            className="text-xs text-muted-foreground font-sans flex items-center gap-1 hover:text-foreground transition-colors px-2 py-1 rounded-full border border-border"
                          >
                            <ExternalLink size={10} />
                            Details
                          </button>
                        )}
                      </div>
                    )}
                  </>
                ) : call.error ? (
                  <p className="text-sm text-muted-foreground font-sans">{call.error}</p>
                ) : (
                  <p className="text-xs text-muted-foreground font-sans">{getStatusText(call.status)}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
