"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Textarea } from "@/components/ui/textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface PromptInputContextValue {
  isLoading: boolean
  value: string
  onValueChange: (value: string) => void
  maxHeight: number
  onSubmit?: () => void
  disabled: boolean
}

const PromptInputContext = React.createContext<PromptInputContextValue | null>(
  null
)

function usePromptInputContext() {
  const ctx = React.useContext(PromptInputContext)
  if (!ctx) {
    throw new Error("PromptInput.* must be used inside <PromptInput>")
  }
  return ctx
}

export type PromptInputProps = {
  isLoading?: boolean
  value: string
  onValueChange: (value: string) => void
  maxHeight?: number
  onSubmit?: () => void
  children: React.ReactNode
  className?: string
  disabled?: boolean
}

export function PromptInput({
  isLoading = false,
  value,
  onValueChange,
  maxHeight = 200,
  onSubmit,
  children,
  className,
  disabled = false,
}: PromptInputProps) {
  return (
    <PromptInputContext.Provider
      value={{
        isLoading,
        value,
        onValueChange,
        maxHeight,
        onSubmit,
        disabled: disabled || isLoading,
      }}
    >
      <TooltipProvider delayDuration={300}>
        <div
          className={cn(
            "flex flex-col bg-card border border-border rounded-2xl shadow-lg shadow-foreground/5 overflow-hidden",
            className
          )}
        >
          {children}
        </div>
      </TooltipProvider>
    </PromptInputContext.Provider>
  )
}

export type PromptInputTextareaProps = Omit<
  React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  "value" | "onChange"
> & {
  disableAutosize?: boolean
}

export function PromptInputTextarea({
  disableAutosize = false,
  onKeyDown,
  className,
  ...props
}: PromptInputTextareaProps) {
  const { value, onValueChange, maxHeight, onSubmit, disabled } =
    usePromptInputContext()
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const adjustHeight = React.useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea || disableAutosize) return

    textarea.style.height = "auto"
    const newHeight = Math.min(textarea.scrollHeight, maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [disableAutosize, maxHeight])

  React.useEffect(() => {
    adjustHeight()
  }, [value, adjustHeight])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      onSubmit?.()
    }
    onKeyDown?.(e)
  }

  return (
    <Textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      className={cn(
        "w-full resize-none border-0 bg-transparent px-4 py-3 text-base focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground min-h-[52px]",
        className
      )}
      rows={1}
      {...props}
    />
  )
}

// Action chips row - like Le Chat's Canvas, Web search, Image generation
export type PromptInputChipsProps = React.HTMLAttributes<HTMLDivElement>

export function PromptInputChips({
  children,
  className,
  ...props
}: PromptInputChipsProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 pb-3 flex-wrap min-h-8",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

// Individual action chip with icon
export type PromptInputChipProps = {
  icon?: React.ReactNode
  children: React.ReactNode
  active?: boolean
  className?: string
} & React.ButtonHTMLAttributes<HTMLButtonElement>

export function PromptInputChip({
  icon,
  children,
  active = false,
  className,
  ...props
}: PromptInputChipProps) {
  return (
    <button
      className={cn(
        "flex items-center gap-1.5 h-8 px-3 rounded-lg text-sm transition-all shrink-0",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:text-foreground hover:bg-muted",
        className
      )}
      {...props}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}

export type PromptInputActionsProps = React.HTMLAttributes<HTMLDivElement>

export function PromptInputActions({
  children,
  className,
  ...props
}: PromptInputActionsProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 ml-auto min-h-8",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export type PromptInputActionProps = {
  tooltip?: string
  children: React.ReactNode
  className?: string
  side?: "top" | "bottom" | "left" | "right"
  onClick?: (e: React.MouseEvent) => void
}

export function PromptInputAction({
  tooltip,
  children,
  className,
  side = "top",
  onClick,
}: PromptInputActionProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClick?.(e)
  }

  if (!tooltip) {
    return (
      <div className={className} onClick={handleClick}>
        {children}
      </div>
    )
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={className} onClick={handleClick}>
          {children}
        </div>
      </TooltipTrigger>
      <TooltipContent side={side}>
        <p>{tooltip}</p>
      </TooltipContent>
    </Tooltip>
  )
}

// Submit button component
export type PromptInputSubmitProps = {
  icon?: React.ReactNode
  loadingIcon?: React.ReactNode
  className?: string
}

export function PromptInputSubmit({
  icon,
  loadingIcon,
  className,
}: PromptInputSubmitProps) {
  const { isLoading, value, onSubmit, disabled } = usePromptInputContext()
  const hasValue = value.trim().length > 0

  return (
    <button
      onClick={onSubmit}
      disabled={disabled || !hasValue}
      className={cn(
        "rounded-xl w-8 h-8 flex items-center justify-center shrink-0 transition-all",
        hasValue && !disabled
          ? "bg-orange-100 text-orange-600 hover:bg-orange-200"
          : "text-muted-foreground/50 cursor-not-allowed",
        className
      )}
    >
      {isLoading ? loadingIcon : icon}
    </button>
  )
}

// Bottom bar container for chips + actions
export type PromptInputBottomBarProps = React.HTMLAttributes<HTMLDivElement>

export function PromptInputBottomBar({
  children,
  className,
  ...props
}: PromptInputBottomBarProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 px-3 pb-3 min-h-8",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
