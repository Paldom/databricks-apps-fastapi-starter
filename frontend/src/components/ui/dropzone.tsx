import { useCallback, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n/client'

export type DropzoneProps = Readonly<{
  onFilesAdded: (files: File[]) => void
  accept?: string
  multiple?: boolean
  maxSize?: number
  className?: string
  disabled?: boolean
  labels?: {
    idle?: string
    active?: string
    accepted?: string
  }
}>

export function Dropzone({
  onFilesAdded,
  accept,
  multiple = true,
  maxSize,
  className,
  disabled = false,
  labels,
}: DropzoneProps) {
  const { t } = useTranslation()
  const [isDragOver, setIsDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const idleLabel = labels?.idle ?? t('document.dropzoneIdle')
  const activeLabel = labels?.active ?? t('document.dropzoneActive')

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLButtonElement>) => {
      e.preventDefault()
      e.stopPropagation()
      if (!disabled) {
        setIsDragOver(true)
      }
    },
    [disabled]
  )

  const handleDragLeave = useCallback(
    (e: React.DragEvent<HTMLButtonElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)
    },
    []
  )

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLButtonElement>) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)

      if (disabled) return

      const files = Array.from(e.dataTransfer.files)
      const validFiles = files.filter((file) => {
        if (maxSize && file.size > maxSize) return false
        if (accept) {
          const acceptedTypes = accept.split(',').map((t) => t.trim())
          const fileType = file.type
          const fileExtension = `.${file.name.split('.').pop()}`
          return acceptedTypes.some(
            (type) =>
              type === fileType ||
              type === fileExtension ||
              (type.endsWith('/*') && fileType.startsWith(type.slice(0, -1)))
          )
        }
        return true
      })

      if (validFiles.length > 0) {
        onFilesAdded(multiple ? validFiles : [validFiles[0]])
      }
    },
    [disabled, maxSize, accept, multiple, onFilesAdded]
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : []
      if (files.length > 0) {
        onFilesAdded(multiple ? files : [files[0]])
      }
      e.target.value = ''
    },
    [multiple, onFilesAdded]
  )

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileInput}
        disabled={disabled}
        tabIndex={-1}
        aria-hidden="true"
        className="sr-only"
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        disabled={disabled}
        className={cn(
          'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors',
          'bg-transparent text-inherit',
          isDragOver
            ? 'border-primary bg-primary/5'
            : 'border-muted-foreground/25 hover:border-muted-foreground/50',
          disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
          className
        )}
      >
        <Upload className="mb-2 h-6 w-6 text-muted-foreground" />
        <span className="block text-sm text-muted-foreground">
          {isDragOver ? activeLabel : idleLabel}
        </span>
        {accept && labels?.accepted && (
          <span className="mt-1 block text-xs text-muted-foreground/70">
            {labels.accepted}
          </span>
        )}
      </button>
    </>
  )
}
