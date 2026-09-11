import '@assistant-ui/react-markdown/styles/dot.css'

import {
  type CodeHeaderProps,
  MarkdownTextPrimitive,
  unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
  useIsMarkdownCodeBlock,
} from '@assistant-ui/react-markdown'
import { Check, Copy } from 'lucide-react'
import { type FC, memo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import remarkGfm from 'remark-gfm'

import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button'
import { cn } from '@/lib/utils'

function MarkdownTextImpl() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      className="aui-md"
      components={defaultComponents}
    />
  )
}

export const MarkdownText = memo(MarkdownTextImpl)

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { t } = useTranslation()
  const { isCopied, copyToClipboard } = useCopyToClipboard()
  const onCopy = () => {
    if (!code || isCopied) return
    copyToClipboard(code)
  }

  return (
    <div className="mt-2.5 flex items-center justify-between rounded-t-lg border border-b-0 border-border/50 bg-muted/50 px-3 py-1.5 text-xs">
      <span className="font-medium lowercase text-muted-foreground">
        {language}
      </span>
      <TooltipIconButton
        tooltip={isCopied ? t('chat.copied') : t('chat.copy')}
        onClick={onCopy}
      >
        {isCopied ? <Check /> : <Copy />}
      </TooltipIconButton>
    </div>
  )
}

const useCopyToClipboard = ({
  copiedDuration = 3000,
}: {
  copiedDuration?: number
} = {}) => {
  const [isCopied, setIsCopied] = useState<boolean>(false)

  const copyToClipboard = (value: string) => {
    if (!value) return

    void navigator.clipboard
      .writeText(value)
      .then(() => {
        setIsCopied(true)
        setTimeout(() => setIsCopied(false), copiedDuration)
      })
      .catch(() => {
        setIsCopied(false)
      })
  }

  return { isCopied, copyToClipboard }
}

const defaultComponents = memoizeMarkdownComponents({
  h1: ({ className, children, ...props }) => (
    <h1
      className={cn(
        'mb-2 scroll-m-20 text-base font-semibold first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ className, children, ...props }) => (
    <h2
      className={cn(
        'mb-1.5 mt-3 scroll-m-20 text-sm font-semibold first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ className, children, ...props }) => (
    <h3
      className={cn(
        'mb-1 mt-2.5 scroll-m-20 text-sm font-semibold first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ className, children, ...props }) => (
    <h4
      className={cn(
        'mb-1 mt-2 scroll-m-20 text-sm font-medium first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h4>
  ),
  h5: ({ className, children, ...props }) => (
    <h5
      className={cn(
        'mb-1 mt-2 text-sm font-medium first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h5>
  ),
  h6: ({ className, children, ...props }) => (
    <h6
      className={cn(
        'mb-1 mt-2 text-sm font-medium first:mt-0 last:mb-0',
        className
      )}
      {...props}
    >
      {children}
    </h6>
  ),
  p: ({ className, ...props }) => (
    <p
      className={cn('my-2.5 leading-normal first:mt-0 last:mb-0', className)}
      {...props}
    />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn(
        'text-primary underline underline-offset-2 hover:text-primary/80',
        className
      )}
      {...props}
    />
  ),
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn(
        'my-2.5 border-l-2 border-muted-foreground/30 pl-3 italic text-muted-foreground',
        className
      )}
      {...props}
    />
  ),
  ul: ({ className, ...props }) => (
    <ul
      className={cn(
        'my-2 ml-4 list-disc marker:text-muted-foreground [&>li]:mt-1',
        className
      )}
      {...props}
    />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn(
        'my-2 ml-4 list-decimal marker:text-muted-foreground [&>li]:mt-1',
        className
      )}
      {...props}
    />
  ),
  hr: ({ className, ...props }) => (
    <hr
      className={cn('my-2 border-muted-foreground/20', className)}
      {...props}
    />
  ),
  table: ({ className, ...props }) => (
    <table
      className={cn(
        'my-2 w-full border-separate border-spacing-0 overflow-y-auto',
        className
      )}
      {...props}
    />
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        'bg-muted px-2 py-1 text-left font-medium first:rounded-tl-lg last:rounded-tr-lg',
        className
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn(
        'border-b border-l border-muted-foreground/20 px-2 py-1 text-left last:border-r',
        className
      )}
      {...props}
    />
  ),
  tr: ({ className, ...props }) => (
    <tr
      className={cn(
        'm-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-bl-lg [&:last-child>td:last-child]:rounded-br-lg',
        className
      )}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn('leading-normal', className)} {...props} />
  ),
  sup: ({ className, ...props }) => (
    <sup
      className={cn('[&>a]:text-xs [&>a]:no-underline', className)}
      {...props}
    />
  ),
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        'overflow-x-auto rounded-b-lg rounded-t-none border border-t-0 border-border/50 bg-muted/30 p-3 text-xs leading-relaxed',
        className
      )}
      {...props}
    />
  ),
  code: function Code({ className, ...props }) {
    const isCodeBlock = useIsMarkdownCodeBlock()
    return (
      <code
        className={cn(
          !isCodeBlock &&
            'rounded-md border border-border/50 bg-muted/50 px-1.5 py-0.5 font-mono text-[0.85em]',
          className
        )}
        {...props}
      />
    )
  },
  CodeHeader,
})
