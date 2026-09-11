import {
  ThreadPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  makeAssistantToolUI,
  useAuiState,
  type ToolCallMessagePartProps,
} from '@assistant-ui/react'
import { useTranslation } from '@/i18n/client'
import { cn } from '@/lib/utils'
import { MarkdownText } from '@/components/assistant-ui/markdown-text'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'

function ThreadMessages() {
  return (
    <ThreadPrimitive.Messages
      components={{
        UserMessage: UserMessage,
        AssistantMessage: AssistantMessage,
      }}
    />
  )
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end py-2">
      <div className="max-w-[80%] rounded-lg bg-primary px-4 py-2 text-primary-foreground">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  )
}

function AssistantMessage() {
  const { t } = useTranslation()
  const status = useAuiState(({ message }) => message.status)
  const error =
    status?.type === 'incomplete' && status.reason === 'error'
      ? status.error
      : undefined
  return (
    <MessagePrimitive.Root className="flex justify-start py-2">
      <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
        <MessagePrimitive.Content
          components={{ Text: MarkdownText, tools: { Fallback: GenericTool } }}
        />
        <MessagePrimitive.Error>
          <p role="alert" className="mt-2 text-destructive">
            {typeof error === 'string' ? error : t('common.error')}
          </p>
        </MessagePrimitive.Error>
      </div>
    </MessagePrimitive.Root>
  )
}

function Composer() {
  const { t } = useTranslation()
  return (
    <ComposerPrimitive.Root className="flex items-end gap-2 border-t bg-background p-4">
      <ComposerPrimitive.Input
        placeholder={t('chat.placeholder')}
        aria-label={t('chat.message')}
        className="flex-1 resize-none rounded-lg border bg-transparent px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        autoFocus
      />
      <ComposerPrimitive.Send asChild>
        <Button aria-label={t('chat.send')} size="icon" className="shrink-0">
          <Send className="h-4 w-4" />
        </Button>
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  )
}

function ThreadEmpty() {
  const { t } = useTranslation()
  return (
    <ThreadPrimitive.Empty>
      <div className="flex h-full items-center justify-center">
        <p className="text-center text-sm text-muted-foreground">
          {t('chat.startConversation')}
        </p>
      </div>
    </ThreadPrimitive.Empty>
  )
}

type AssistantThreadProps = Readonly<{ className?: string }>

export function AssistantThread({ className }: AssistantThreadProps) {
  return (
    <ThreadPrimitive.Root className={cn('flex h-full flex-col', className)}>
      <KnowledgeToolUI />
      <GenieToolUI />
      <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto p-4">
        <ThreadEmpty />
        <ThreadMessages />
      </ThreadPrimitive.Viewport>
      <Composer />
    </ThreadPrimitive.Root>
  )
}

function resultText(result: unknown): string {
  if (typeof result === 'string') return result
  if (
    result &&
    typeof result === 'object' &&
    'text' in result &&
    typeof result.text === 'string'
  )
    return result.text
  return JSON.stringify(result, null, 2) ?? ''
}

function KnowledgeResult({ result, isError }: ToolCallMessagePartProps) {
  const { t } = useTranslation()
  const text = resultText(result)
  const snippets = text
    .split(/(?=^\s*\[\d+\]|^\s*\d+[.)]\s)/m)
    .filter((snippet) => snippet.trim())
  return (
    <section aria-label={t('chat.sources')} className="my-2 space-y-2">
      <h3 className="font-medium">{t('chat.sources')}</h3>
      {isError && <p role="alert">{t('chat.toolError')}</p>}
      {result === undefined ? (
        <p role="status">{t('common.loading')}</p>
      ) : (
        <ul className="space-y-2">
          {snippets.map((snippet, index) => (
            <li key={index} className="whitespace-pre-wrap break-words text-sm">
              {snippet}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function GenieResult({ result, isError }: ToolCallMessagePartProps) {
  const { t } = useTranslation()
  const sql =
    result && typeof result === 'object' && 'sql' in result
      ? result.sql
      : undefined
  return (
    <section aria-label={t('chat.genie')} className="my-2 space-y-2">
      <h3 className="font-medium">{t('chat.genie')}</h3>
      {isError && <p role="alert">{t('chat.toolError')}</p>}
      {result === undefined ? (
        <p role="status">{t('common.loading')}</p>
      ) : (
        <pre className="whitespace-pre-wrap break-words text-sm">
          {resultText(result)}
        </pre>
      )}
      {typeof sql === 'string' && (
        <>
          <h4>{t('chat.sql')}</h4>
          <pre className="whitespace-pre-wrap break-words text-sm">{sql}</pre>
        </>
      )}
    </section>
  )
}

function GenericTool({
  toolName,
  argsText,
  result,
  isError,
}: ToolCallMessagePartProps) {
  const { t } = useTranslation()
  return (
    <details className="my-2 rounded border p-2 text-sm">
      <summary className="cursor-pointer rounded focus-visible:ring-2 focus-visible:ring-ring">
        {toolName}
      </summary>
      <h4>{t('chat.arguments')}</h4>
      <pre className="whitespace-pre-wrap break-words">{argsText}</pre>
      <h4>{t('chat.result')}</h4>
      <pre className="whitespace-pre-wrap break-words">
        {result === undefined ? t('common.loading') : resultText(result)}
      </pre>
      {isError && <p role="alert">{t('chat.toolError')}</p>}
    </details>
  )
}

const KnowledgeToolUI = makeAssistantToolUI({
  toolName: 'knowledge_assistant',
  render: KnowledgeResult,
})
const GenieToolUI = makeAssistantToolUI({
  toolName: 'genie',
  render: GenieResult,
})
