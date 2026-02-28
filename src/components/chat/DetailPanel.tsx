import { useState } from 'react';
import { Phone, Check, X, Clock, MapPin, Star } from 'lucide-react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../ui/sheet';
import type { Message, CallStatus } from '../../types/chat';

interface DetailPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  message: Message | null;
}

function getStatusLabel(status: CallStatus['status']): string {
  const map: Record<CallStatus['status'], string> = {
    pending: 'Waiting',
    ringing: 'Ringing',
    connected: 'On call',
    complete: 'Complete',
    failed: 'Failed',
    no_answer: 'No answer',
    busy: 'Busy',
  };
  return map[status] || status;
}

function getStatusColor(status: CallStatus['status']): string {
  switch (status) {
    case 'complete': return 'text-emerald-600';
    case 'failed': case 'no_answer': case 'busy': return 'text-muted-foreground';
    case 'ringing': return 'text-amber-500';
    case 'connected': return 'text-foreground';
    default: return 'text-muted-foreground';
  }
}

export default function DetailPanel({ open, onOpenChange, message }: DetailPanelProps) {
  const [showRawData, setShowRawData] = useState(false);

  if (!message) return null;

  const callStatuses = message.callStatuses ?? [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="overflow-y-auto w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-sans text-base">Call Details</SheetTitle>
          <SheetDescription className="font-sans text-sm">
            {callStatuses.length} business{callStatuses.length !== 1 ? 'es' : ''} contacted
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          {callStatuses.map((call) => (
            <div
              key={call.phone || call.business}
              className="border border-border rounded-xl p-4 space-y-3"
            >
              {/* Business info */}
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground font-sans">{call.business}</p>
                  {call.phone && (
                    <a
                      href={`tel:${call.phone}`}
                      className="text-xs text-muted-foreground font-sans hover:text-foreground transition-colors flex items-center gap-1 mt-0.5"
                    >
                      <Phone size={10} />
                      {call.phone}
                    </a>
                  )}
                  {call.address && (
                    <p className="text-xs text-muted-foreground font-sans flex items-center gap-1 mt-0.5">
                      <MapPin size={10} />
                      {call.address}
                    </p>
                  )}
                  {call.rating != null && (
                    <p className="text-xs text-muted-foreground font-sans flex items-center gap-1 mt-0.5">
                      <Star size={10} />
                      {call.rating.toFixed(1)}
                    </p>
                  )}
                </div>
                <span className={`text-xs font-medium font-sans ${getStatusColor(call.status)}`}>
                  {getStatusLabel(call.status)}
                </span>
              </div>

              {/* Result */}
              {call.result && (
                <div className="bg-muted/50 rounded-lg p-3">
                  <p className="text-xs font-medium text-muted-foreground font-sans mb-1">Result</p>
                  <p className="text-sm text-foreground font-sans">{call.result}</p>
                </div>
              )}

              {/* Error */}
              {call.error && (
                <div className="bg-destructive/5 rounded-lg p-3">
                  <p className="text-xs font-medium text-muted-foreground font-sans mb-1">Error</p>
                  <p className="text-sm text-muted-foreground font-sans">{call.error}</p>
                </div>
              )}

              {/* Transcript placeholder */}
              <div className="border-t border-border pt-3">
                <p className="text-xs text-muted-foreground/60 font-sans italic">
                  Call transcript not available yet
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Nerd view toggle */}
        <div className="mt-6 pt-4 border-t border-border">
          <button
            onClick={() => setShowRawData(!showRawData)}
            className="text-xs text-muted-foreground font-sans font-medium hover:text-foreground transition-colors"
          >
            {showRawData ? 'Hide' : 'Show'} raw data
          </button>
          {showRawData && (
            <pre className="mt-3 bg-muted rounded-xl p-4 text-xs font-mono overflow-auto max-h-64 text-foreground">
              {JSON.stringify(callStatuses, null, 2)}
            </pre>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
