/**
 * InboxPreviewCard — displays Gmail inbox summary results.
 *
 * Rendered inside AIChat.tsx when message.agent === 'inbox'.
 * Shows: auth prompt, loading states, or structured summary card.
 */

import { Mail, ExternalLink, AlertCircle, Loader2, Inbox } from 'lucide-react';
import type { InboxSummary } from '../../hooks/useInboxStream';

interface InboxPreviewCardProps {
  status: 'checking' | 'auth_required' | 'fetching' | 'summarizing' | 'complete' | 'error';
  message?: string;
  authUrl?: string | null;
  summary?: InboxSummary | null;
  emailCount?: number | null;
  error?: string | null;
}

export function InboxPreviewCard({
  status,
  message,
  authUrl,
  summary,
  emailCount,
  error,
}: InboxPreviewCardProps) {
  // Auth required
  if (status === 'auth_required' && authUrl) {
    return (
      <div className="w-full max-w-3xl mx-auto rounded-xl border border-amber-200/80 bg-amber-50/50 overflow-hidden mt-3 shadow-sm">
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-sm shrink-0">
            <Mail size={18} className="text-white" />
          </div>
          <div className="flex-1">
            <p className="text-sm text-gray-800 font-medium">Connect your Gmail</p>
            <p className="text-xs text-gray-500 mt-0.5">One-time setup to check your inbox</p>
          </div>
          <a
            href={authUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity shadow-sm"
          >
            Connect Gmail
            <ExternalLink size={13} />
          </a>
        </div>
      </div>
    );
  }

  // Loading states
  if (status === 'checking' || status === 'fetching' || status === 'summarizing') {
    return (
      <div className="w-full max-w-3xl mx-auto rounded-xl border border-border bg-card overflow-hidden mt-3 shadow-sm">
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center shadow-sm shrink-0">
            <Loader2 size={18} className="text-white animate-spin" />
          </div>
          <div>
            <p className="text-sm text-foreground font-medium">
              {status === 'checking' && 'Checking Gmail connection...'}
              {status === 'fetching' && 'Fetching your emails...'}
              {status === 'summarizing' && `Summarizing ${emailCount ?? ''} emails...`}
            </p>
            {message && (
              <p className="text-xs text-muted-foreground mt-0.5">{message}</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Error
  if (status === 'error') {
    return (
      <div className="w-full max-w-3xl mx-auto rounded-xl border border-red-200/80 bg-red-50/50 overflow-hidden mt-3 shadow-sm">
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-400 to-red-500 flex items-center justify-center shadow-sm shrink-0">
            <AlertCircle size={18} className="text-white" />
          </div>
          <div>
            <p className="text-sm text-gray-800 font-medium">Couldn't check your inbox</p>
            <p className="text-xs text-gray-500 mt-0.5">{error || 'Something went wrong'}</p>
          </div>
        </div>
      </div>
    );
  }

  // Complete — summary card
  if (status === 'complete' && summary) {
    return (
      <div className="w-full max-w-3xl mx-auto rounded-xl shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)] border border-gray-200/80 bg-white overflow-hidden text-gray-800 font-sans mt-3">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200/80 bg-gradient-to-r from-blue-500/10 to-indigo-500/10">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-b from-blue-500 to-indigo-600 flex items-center justify-center shadow-sm">
              <Inbox size={14} className="text-white" />
            </div>
            <span className="font-semibold text-[17px] text-gray-900 tracking-tight">Inbox</span>
          </div>
          <div className="flex items-center gap-2">
            {summary.needs_action && (
              <span className="px-2 py-0.5 text-[11px] font-semibold bg-amber-100 text-amber-700 rounded-full">
                Action needed
              </span>
            )}
            <span className="text-sm text-gray-500 font-medium">
              {summary.important_count} important
            </span>
          </div>
        </div>

        {/* Updates list */}
        <div className="px-4 py-3 flex flex-col gap-2">
          {summary.top_updates.map((update, idx) => (
            <div key={idx} className="flex items-start gap-2.5">
              <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
              <p className="text-[14px] text-gray-700 leading-relaxed">{update}</p>
            </div>
          ))}
        </div>

        {/* Sender highlights */}
        {summary.sender_highlights && summary.sender_highlights.length > 0 && (
          <div className="px-4 py-2.5 border-t border-gray-100 flex flex-wrap gap-1.5">
            {summary.sender_highlights.map((sender, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 text-[12px] text-gray-600 bg-gray-100 rounded-full"
              >
                {sender}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="px-4 py-2.5 border-t border-gray-200/80 bg-gray-50/50 flex items-center justify-between">
          <span className="text-[12px] text-gray-400">{summary.time_range || 'Last 24 hours'}</span>
          <a
            href="https://mail.google.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[12px] text-blue-500 font-medium flex items-center gap-1 hover:opacity-70 transition-opacity"
          >
            Open Gmail <ExternalLink size={10} />
          </a>
        </div>
      </div>
    );
  }

  return null;
}
