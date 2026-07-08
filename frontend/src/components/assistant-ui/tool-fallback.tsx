import type { ToolCallMessagePartProps } from '@assistant-ui/react'

/**
 * Compact fallback renderer for tool calls without a registered UI.
 * Tool names/args are technical output, so they are shown verbatim (no i18n).
 */
export function ToolFallback({
  toolName,
  argsText,
}: Readonly<ToolCallMessagePartProps>) {
  return (
    <div className="my-2 rounded-md border border-border/50 bg-muted/30 px-3 py-2 font-mono text-xs">
      <span className="font-semibold">{toolName}</span>
      {argsText && (
        <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-muted-foreground">
          {argsText}
        </pre>
      )}
    </div>
  )
}
