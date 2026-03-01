"use client"

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { cn } from "@/lib/utils"
import { createContext, useContext } from "react"
import { ExternalLink } from "lucide-react"

const SourceContext = createContext<{
  href: string
  domain: string
} | null>(null)

function useSourceContext() {
  const ctx = useContext(SourceContext)
  if (!ctx) throw new Error("Source.* must be used inside <Source>")
  return ctx
}

export type SourceProps = {
  href: string
  children: React.ReactNode
}

export function Source({ href, children }: SourceProps) {
  let domain = ""
  try {
    domain = new URL(href).hostname
  } catch {
    domain = href.split("/").pop() || href
  }

  return (
    <SourceContext.Provider value={{ href, domain }}>
      <HoverCard openDelay={150} closeDelay={0}>
        {children}
      </HoverCard>
    </SourceContext.Provider>
  )
}

export type SourceTriggerProps = {
  label?: string | number
  showFavicon?: boolean
  className?: string
}

export function SourceTrigger({
  label,
  showFavicon = false,
  className,
}: SourceTriggerProps) {
  const { href, domain } = useSourceContext()
  const labelToShow = label ?? domain.replace("www.", "")

  return (
    <HoverCardTrigger asChild>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-1 bg-muted text-muted-foreground hover:bg-muted-foreground/20 rounded-md text-xs font-medium px-1.5 py-0.5 transition-colors cursor-pointer",
          showFavicon ? "pr-2 pl-1" : "px-1.5",
          className
        )}
      >
        {showFavicon && (
          <img
            src={`https://www.google.com/s2/favicons?sz=64&domain_url=${domain}`}
            alt="favicon"
            width={14}
            height={14}
            className="size-3.5 rounded-full"
          />
        )}
        <span className="truncate tabular-nums text-center font-normal">
          {labelToShow}
        </span>
      </a>
    </HoverCardTrigger>
  )
}

export type SourceContentProps = {
  title: string
  description?: string
  className?: string
}

export function SourceContent({
  title,
  description,
  className,
}: SourceContentProps) {
  const { href, domain } = useSourceContext()

  return (
    <HoverCardContent className={cn("w-80 p-0 shadow-lg", className)}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="block p-3 space-y-2 hover:bg-muted/50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-1.5">
          <img
            src={`https://www.google.com/s2/favicons?sz=64&domain_url=${domain}`}
            alt="favicon"
            width={16}
            height={16}
            className="size-4 rounded"
          />
          <div className="text-muted-foreground truncate text-sm">
            {domain.replace("www.", "")}
          </div>
          <ExternalLink size={12} className="text-muted-foreground ml-auto" />
        </div>
        <div className="line-clamp-2 text-sm font-medium">{title}</div>
        {description && (
          <div className="text-muted-foreground line-clamp-2 text-sm">
            {description}
          </div>
        )}
      </a>
    </HoverCardContent>
  )
}

// Convenience component for listing multiple sources
export type SourceListProps = {
  sources: Array<{
    href: string
    title: string
    description?: string
  }>
  className?: string
}

export function SourceList({ sources, className }: SourceListProps) {
  if (!sources || sources.length === 0) return null

  return (
    <div className={cn("flex flex-wrap gap-1.5 mt-3", className)}>
      <span className="text-xs text-muted-foreground">Sources:</span>
      {sources.map((source, idx) => (
        <Source key={idx} href={source.href}>
          <SourceTrigger label={idx + 1} showFavicon />
          <SourceContent title={source.title} description={source.description} />
        </Source>
      ))}
    </div>
  )
}
