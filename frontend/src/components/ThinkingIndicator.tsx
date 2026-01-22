interface ThinkingIndicatorProps {
  text?: string
}

export function ThinkingIndicator({ text = 'Thinking' }: ThinkingIndicatorProps) {
  return (
    <div className="text-xs text-gray-500 dark:text-gray-400 italic flex items-center">
      <span>{text}</span>
      <span className="inline-flex ml-0.5">
        <span className="animate-fade-in-dot" style={{ animationDelay: '0s' }}>
          .
        </span>
        <span className="animate-fade-in-dot" style={{ animationDelay: '0.2s' }}>
          .
        </span>
        <span className="animate-fade-in-dot" style={{ animationDelay: '0.4s' }}>
          .
        </span>
      </span>
    </div>
  )
}
