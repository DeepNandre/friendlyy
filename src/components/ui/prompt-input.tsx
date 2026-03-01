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
        "w-full resize-none border-0 bg-transparent px-4 py-3 text-sm focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground min-h-[44px]",
        className
      )}
      rows={1}
      {...props}
    />
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
        "flex items-center gap-2 px-3 pb-3",
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

  return (
    <button
      onClick={onSubmit}
      disabled={disabled || !value.trim()}
      className={cn(
        "ml-auto bg-foreground hover:bg-foreground/90 disabled:bg-foreground/30 disabled:cursor-not-allowed text-background rounded-xl w-9 h-9 flex items-center justify-center shrink-0 transition-all",
        className
      )}
    >
      {isLoading ? loadingIcon : icon}
    </button>
  )
}
