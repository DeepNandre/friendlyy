"use client"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import { ChevronDown, Check, Loader2, Circle } from "lucide-react"

// StepsItem Component
export type StepsItemProps = React.ComponentProps<"div"> & {
  status?: "pending" | "in_progress" | "complete" | "error"
}

export const StepsItem = ({
  children,
  className,
  status = "pending",
  ...props
}: StepsItemProps) => {
  const getStatusIcon = () => {
    switch (status) {
      case "complete":
        return <Check size={14} className="text-green-500" />
      case "in_progress":
        return <Loader2 size={14} className="text-violet-500 animate-spin" />
      case "error":
        return <Circle size={14} className="text-red-500 fill-red-500" />
      default:
        return <Circle size={14} className="text-muted-foreground/40" />
    }
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2 text-sm",
        status === "complete" ? "text-foreground" : "text-muted-foreground",
        className
      )}
      {...props}
    >
      {getStatusIcon()}
      {children}
    </div>
  )
}

// StepsTrigger Component
export type StepsTriggerProps = React.ComponentProps<
  typeof CollapsibleTrigger
> & {
  leftIcon?: React.ReactNode
  swapIconOnHover?: boolean
}

export const StepsTrigger = ({
  children,
  className,
  leftIcon,
  swapIconOnHover = true,
  ...props
}: StepsTriggerProps) => (
  <CollapsibleTrigger
    className={cn(
      "group text-muted-foreground hover:text-foreground flex w-full cursor-pointer items-center justify-start gap-1.5 text-sm transition-colors",
      className
    )}
    {...props}
  >
    <div className="flex items-center gap-2">
      {leftIcon ? (
        <span className="relative inline-flex size-4 items-center justify-center">
          <span
            className={cn(
              "transition-opacity",
              swapIconOnHover && "group-hover:opacity-0"
            )}
          >
            {leftIcon}
          </span>
          {swapIconOnHover && (
            <ChevronDown className="absolute size-4 opacity-0 transition-all group-hover:opacity-100 group-data-[state=open]:rotate-180" />
          )}
        </span>
      ) : null}
      <span>{children}</span>
    </div>
    {!leftIcon && (
      <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" />
    )}
  </CollapsibleTrigger>
)

// StepsContent Component
export type StepsContentProps = React.ComponentProps<
  typeof CollapsibleContent
> & {
  bar?: React.ReactNode
  showBar?: boolean
}

export const StepsContent = ({
  children,
  className,
  bar,
  showBar = true,
  ...props
}: StepsContentProps) => {
  return (
    <CollapsibleContent
      className={cn(
        "text-foreground overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down",
        className
      )}
      {...props}
    >
      <div className="mt-2 grid max-w-full min-w-0 grid-cols-[min-content_minmax(0,1fr)] items-start gap-x-3">
        {showBar && (
          <div className="min-w-0 self-stretch">{bar ?? <StepsBar />}</div>
        )}
        <div className={cn("min-w-0 space-y-1.5", !showBar && "col-span-2")}>
          {children}
        </div>
      </div>
    </CollapsibleContent>
  )
}

// StepsBar Component
export type StepsBarProps = React.HTMLAttributes<HTMLDivElement>

export const StepsBar = ({ className, ...props }: StepsBarProps) => (
  <div
    className={cn("bg-muted h-full w-[2px] rounded-full ml-1.5", className)}
    aria-hidden
    {...props}
  />
)

// Main Steps Component
export type StepsProps = React.ComponentProps<typeof Collapsible>

export function Steps({
  defaultOpen = true,
  className,
  ...props
}: StepsProps) {
  return (
    <Collapsible
      className={cn(className)}
      defaultOpen={defaultOpen}
      {...props}
    />
  )
}
