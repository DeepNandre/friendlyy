"use client"

import { cn } from "@/lib/utils"
import { marked } from "marked"
import { memo, useId, useMemo } from "react"
import ReactMarkdown, { Components } from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"

export type MarkdownProps = {
  children: string
  id?: string
  className?: string
  components?: Partial<Components>
}

function parseMarkdownIntoBlocks(markdown: string): string[] {
  const tokens = marked.lexer(markdown)
  return tokens.map((token) => token.raw)
}

const INITIAL_COMPONENTS: Partial<Components> = {
  code: function CodeComponent({ className, children, ...props }) {
    return (
      <code
        className={cn(
          "bg-muted rounded-sm px-1.5 py-0.5 font-mono text-sm",
          className
        )}
        {...props}
      >
        {children}
      </code>
    )
  },
  pre: function PreComponent({ children }) {
    return (
      <pre className="bg-muted rounded-lg p-4 overflow-x-auto my-3">
        {children}
      </pre>
    )
  },
  a: function LinkComponent({ href, children, ...props }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline underline-offset-2 hover:opacity-80 transition-opacity"
        {...props}
      >
        {children}
      </a>
    )
  },
  p: function ParagraphComponent({ children, ...props }) {
    return (
      <p className="leading-relaxed mb-3 last:mb-0" {...props}>
        {children}
      </p>
    )
  },
  ul: function UlComponent({ children, ...props }) {
    return (
      <ul className="list-disc list-inside mb-3 space-y-1" {...props}>
        {children}
      </ul>
    )
  },
  ol: function OlComponent({ children, ...props }) {
    return (
      <ol className="list-decimal list-inside mb-3 space-y-1" {...props}>
        {children}
      </ol>
    )
  },
  li: function LiComponent({ children, ...props }) {
    return (
      <li className="leading-relaxed" {...props}>
        {children}
      </li>
    )
  },
  h1: function H1Component({ children, ...props }) {
    return (
      <h1 className="text-xl font-semibold mb-3 mt-4 first:mt-0" {...props}>
        {children}
      </h1>
    )
  },
  h2: function H2Component({ children, ...props }) {
    return (
      <h2 className="text-lg font-semibold mb-2 mt-4 first:mt-0" {...props}>
        {children}
      </h2>
    )
  },
  h3: function H3Component({ children, ...props }) {
    return (
      <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0" {...props}>
        {children}
      </h3>
    )
  },
  blockquote: function BlockquoteComponent({ children, ...props }) {
    return (
      <blockquote
        className="border-l-2 border-muted-foreground/30 pl-4 italic my-3"
        {...props}
      >
        {children}
      </blockquote>
    )
  },
  strong: function StrongComponent({ children, ...props }) {
    return (
      <strong className="font-semibold" {...props}>
        {children}
      </strong>
    )
  },
}

const MemoizedMarkdownBlock = memo(
  function MarkdownBlock({
    content,
    components = INITIAL_COMPONENTS,
  }: {
    content: string
    components?: Partial<Components>
  }) {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    )
  },
  function propsAreEqual(prevProps, nextProps) {
    return prevProps.content === nextProps.content
  }
)

function MarkdownComponent({
  children,
  id,
  className,
  components = INITIAL_COMPONENTS,
}: MarkdownProps) {
  const generatedId = useId()
  const blockId = id ?? generatedId
  const blocks = useMemo(() => parseMarkdownIntoBlocks(children), [children])

  return (
    <div className={cn("text-[15px] font-sans", className)}>
      {blocks.map((block, index) => (
        <MemoizedMarkdownBlock
          key={`${blockId}-block-${index}`}
          content={block}
          components={components}
        />
      ))}
    </div>
  )
}

const Markdown = memo(MarkdownComponent)
Markdown.displayName = "Markdown"

export { Markdown }
