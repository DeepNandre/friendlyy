"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Check } from "lucide-react"

export interface ModelOption {
  id: string
  name: string
  description?: string
  icon?: React.ReactNode
  provider?: string
}

export interface ModelSelectorProps {
  models: ModelOption[]
  selectedModel: string
  onModelChange: (modelId: string) => void
  className?: string
}

// Mistral logo SVG
const MistralLogo = () => (
  <svg width="16" height="16" viewBox="0 0 256 233" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect y="0" width="46.5" height="46.5" fill="#F7D046"/>
    <rect x="46.5" y="0" width="46.5" height="46.5" fill="black"/>
    <rect x="93" y="0" width="46.5" height="46.5" fill="black"/>
    <rect x="139.5" y="0" width="46.5" height="46.5" fill="black"/>
    <rect x="186" y="0" width="46.5" height="46.5" fill="black"/>
    <rect x="209.5" y="0" width="46.5" height="46.5" fill="#F7D046"/>
    <rect y="46.5" width="46.5" height="46.5" fill="black"/>
    <rect x="93" y="46.5" width="46.5" height="46.5" fill="#F7D046"/>
    <rect x="139.5" y="46.5" width="46.5" height="46.5" fill="#F7D046"/>
    <rect x="209.5" y="46.5" width="46.5" height="46.5" fill="black"/>
    <rect y="93" width="46.5" height="46.5" fill="black"/>
    <rect x="46.5" y="93" width="46.5" height="46.5" fill="#F2A73B"/>
    <rect x="93" y="93" width="46.5" height="46.5" fill="black"/>
    <rect x="139.5" y="93" width="46.5" height="46.5" fill="black"/>
    <rect x="186" y="93" width="46.5" height="46.5" fill="#F2A73B"/>
    <rect x="209.5" y="93" width="46.5" height="46.5" fill="black"/>
    <rect y="139.5" width="46.5" height="46.5" fill="black"/>
    <rect x="93" y="139.5" width="46.5" height="46.5" fill="#EE792F"/>
    <rect x="139.5" y="139.5" width="46.5" height="46.5" fill="#EE792F"/>
    <rect x="209.5" y="139.5" width="46.5" height="46.5" fill="black"/>
    <rect y="186" width="46.5" height="46.5" fill="#EA5D2A"/>
    <rect x="46.5" y="186" width="46.5" height="46.5" fill="black"/>
    <rect x="93" y="186" width="46.5" height="46.5" fill="black"/>
    <rect x="139.5" y="186" width="46.5" height="46.5" fill="black"/>
    <rect x="186" y="186" width="46.5" height="46.5" fill="black"/>
    <rect x="209.5" y="186" width="46.5" height="46.5" fill="#EA5D2A"/>
  </svg>
)

// NVIDIA logo
const NvidiaLogo = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8.948 8.798v-1.43a6.7 6.7 0 0 1 .424-.018c3.922-.124 6.493 3.374 6.493 3.374s-2.774 3.851-5.75 3.851c-.424 0-.83-.062-1.167-.169v-5.608zm0-4.595V2.862l.34-.01c5.53-.173 9.248 4.429 9.248 4.429s-4.283 5.47-8.043 5.47c-.536 0-1.05-.079-1.545-.229V8.798c1.678.16 2.012.947 3.03 2.355l2.273-1.89s-1.607-2.021-4.132-2.021c-.44 0-.82.044-1.17.116V4.203zM8.948 19.25V17.4c.404.112.834.17 1.284.17 2.49 0 4.3-1.933 4.3-1.933l3.5 2.753s-2.89 3.49-7.467 3.49c-.568 0-1.114-.077-1.617-.224v-2.406zm-1.324-9.12V7.362H5.87C2.891 8.93 2 12.327 2 12.327s1.95 4.6 6.05 5.187v-2.093c-2.537-.5-3.675-2.81-3.675-2.81s.876-1.766 3.25-2.483z" fill="#76B900"/>
  </svg>
)

export function ModelSelector({
  models,
  selectedModel,
  onModelChange,
  className,
}: ModelSelectorProps) {
  return (
    <div className={cn("flex items-center justify-center gap-1 flex-wrap", className)}>
      {models.map((model) => {
        const isSelected = selectedModel === model.id
        return (
          <button
            key={model.id}
            onClick={() => onModelChange(model.id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all",
              isSelected
                ? "bg-foreground text-background shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {model.icon}
            <span>{model.name}</span>
            {isSelected && <Check size={14} className="ml-0.5" />}
          </button>
        )
      })}
    </div>
  )
}

// Pre-configured Mistral models
export const MISTRAL_MODELS: ModelOption[] = [
  {
    id: "mistral-nemo",
    name: "Mistral Nemo",
    description: "Fast and efficient for general tasks",
    provider: "nvidia",
    icon: <NvidiaLogo />,
  },
  {
    id: "mixtral-8x7b",
    name: "Mixtral 8x7B",
    description: "Powerful mixture of experts model",
    provider: "nvidia",
    icon: <NvidiaLogo />,
  },
  {
    id: "mistral-small",
    name: "Mistral Small",
    description: "Balanced performance and speed",
    provider: "mistral",
    icon: <MistralLogo />,
  },
  {
    id: "devstral-small",
    name: "Devstral",
    description: "Optimized for coding tasks",
    provider: "mistral",
    icon: <MistralLogo />,
  },
]

export { MistralLogo, NvidiaLogo }
