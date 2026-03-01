"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import {
  MessageSquare,
  Phone,
  Code,
  Trash2,
  Plus,
  ChevronLeft,
  Search,
  MoreHorizontal,
} from "lucide-react"

export interface ChatSession {
  id: string
  title: string
  preview: string
  timestamp: Date
  type: 'chat' | 'blitz' | 'build'
  messages: any[]
}

export interface ChatHistoryProps {
  sessions: ChatSession[]
  currentSessionId: string | null
  onSelectSession: (sessionId: string) => void
  onNewChat: () => void
  onDeleteSession: (sessionId: string) => void
  isOpen: boolean
  onClose: () => void
  filter: 'all' | 'blitz' | 'build'
  onFilterChange: (filter: 'all' | 'blitz' | 'build') => void
}

const getSessionIcon = (type: ChatSession['type']) => {
  switch (type) {
    case 'blitz':
      return <Phone size={14} className="text-green-500" />
    case 'build':
      return <Code size={14} className="text-violet-500" />
    default:
      return <MessageSquare size={14} className="text-muted-foreground" />
  }
}

const formatDate = (date: Date) => {
  const now = new Date()
  const d = new Date(date)
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function ChatHistory({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isOpen,
  onClose,
  filter,
  onFilterChange,
}: ChatHistoryProps) {
  const [searchQuery, setSearchQuery] = React.useState('')
  const [hoveredSession, setHoveredSession] = React.useState<string | null>(null)

  const filteredSessions = React.useMemo(() => {
    let filtered = sessions

    // Apply type filter
    if (filter !== 'all') {
      filtered = filtered.filter(s => s.type === filter)
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(s =>
        s.title.toLowerCase().includes(query) ||
        s.preview.toLowerCase().includes(query)
      )
    }

    // Sort by timestamp (newest first)
    return filtered.sort((a, b) =>
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    )
  }, [sessions, filter, searchQuery])

  // Group sessions by date
  const groupedSessions = React.useMemo(() => {
    const groups: { [key: string]: ChatSession[] } = {}

    filteredSessions.forEach(session => {
      const dateKey = formatDate(session.timestamp)
      if (!groups[dateKey]) {
        groups[dateKey] = []
      }
      groups[dateKey].push(session)
    })

    return groups
  }, [filteredSessions])

  if (!isOpen) return null

  return (
    <div className="w-72 h-full border-r border-border bg-card flex flex-col shrink-0">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-foreground text-sm">Chat History</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-muted rounded-lg transition-colors text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft size={18} />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-foreground text-background rounded-xl text-sm font-medium hover:bg-foreground/90 transition-colors"
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="px-4 py-2">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-muted rounded-lg border-0 focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="px-4 py-2 flex gap-1">
        {(['all', 'blitz', 'build'] as const).map((f) => (
          <button
            key={f}
            onClick={() => onFilterChange(f)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              filter === f
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {f === 'all' ? 'All' : f === 'blitz' ? 'Calls' : 'Builds'}
          </button>
        ))}
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {Object.keys(groupedSessions).length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-center px-4">
            <MessageSquare size={24} className="text-muted-foreground/50 mb-2" />
            <p className="text-sm text-muted-foreground">
              {searchQuery ? 'No chats found' : 'No chat history yet'}
            </p>
          </div>
        ) : (
          Object.entries(groupedSessions).map(([dateKey, dateSessions]) => (
            <div key={dateKey} className="mb-4">
              <p className="text-xs text-muted-foreground font-medium px-2 mb-1">
                {dateKey}
              </p>
              {dateSessions.map((session) => (
                <div
                  key={session.id}
                  className={cn(
                    "group relative flex items-start gap-2 px-2 py-2.5 rounded-lg cursor-pointer transition-colors mb-0.5",
                    currentSessionId === session.id
                      ? "bg-accent"
                      : "hover:bg-muted"
                  )}
                  onClick={() => onSelectSession(session.id)}
                  onMouseEnter={() => setHoveredSession(session.id)}
                  onMouseLeave={() => setHoveredSession(null)}
                >
                  <div className="mt-0.5">
                    {getSessionIcon(session.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {session.title}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {session.preview}
                    </p>
                  </div>

                  {/* Delete button on hover */}
                  {hoveredSession === session.id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onDeleteSession(session.id)
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-destructive/10 rounded transition-colors text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <p className="text-[10px] text-muted-foreground text-center">
          {sessions.length} conversations saved locally
        </p>
      </div>
    </div>
  )
}

// Hook for managing chat history with localStorage
export function useChatHistory() {
  const STORAGE_KEY = 'friendly-chat-history'

  const [sessions, setSessions] = React.useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null)
  const [isLoaded, setIsLoaded] = React.useState(false)

  // Load from localStorage on mount
  React.useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Convert timestamp strings back to Date objects
        const sessionsWithDates = parsed.map((s: any) => ({
          ...s,
          timestamp: new Date(s.timestamp)
        }))
        setSessions(sessionsWithDates)
      }
    } catch (e) {
      console.error('Failed to load chat history:', e)
    }
    setIsLoaded(true)
  }, [])

  // Save to localStorage whenever sessions change
  React.useEffect(() => {
    if (!isLoaded) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
    } catch (e) {
      console.error('Failed to save chat history:', e)
    }
  }, [sessions, isLoaded])

  const createSession = React.useCallback((type: ChatSession['type'] = 'chat'): ChatSession => {
    const newSession: ChatSession = {
      id: `session-${Date.now()}`,
      title: 'New Chat',
      preview: '',
      timestamp: new Date(),
      type,
      messages: [],
    }
    setSessions(prev => [newSession, ...prev])
    setCurrentSessionId(newSession.id)
    return newSession
  }, [])

  const updateSession = React.useCallback((sessionId: string, updates: Partial<ChatSession>) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId ? { ...s, ...updates, timestamp: new Date() } : s
    ))
  }, [])

  const deleteSession = React.useCallback((sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId))
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null)
    }
  }, [currentSessionId])

  const selectSession = React.useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId)
  }, [])

  const getCurrentSession = React.useCallback(() => {
    return sessions.find(s => s.id === currentSessionId) || null
  }, [sessions, currentSessionId])

  const clearHistory = React.useCallback(() => {
    setSessions([])
    setCurrentSessionId(null)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return {
    sessions,
    currentSessionId,
    isLoaded,
    createSession,
    updateSession,
    deleteSession,
    selectSession,
    getCurrentSession,
    clearHistory,
    setCurrentSessionId,
  }
}

// Helper to generate a title from the first user message
export function generateSessionTitle(message: string): string {
  const cleaned = message.trim()
  if (cleaned.length <= 40) return cleaned
  return cleaned.substring(0, 40) + '...'
}

// Helper to determine session type from agent
export function getSessionType(agent: string | null): ChatSession['type'] {
  if (agent === 'blitz') return 'blitz'
  if (agent === 'build') return 'build'
  return 'chat'
}
