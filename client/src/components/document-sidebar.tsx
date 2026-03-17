import * as React from 'react'
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Trash2,
  X,
  FileText,
  Loader2,
} from 'lucide-react'
import { useTranslation } from '@/i18n/client'
import { useUIStore } from '@/shared/store/ui'
import { Button } from '@/components/ui/button'
import { Dropzone } from '@/components/ui/dropzone'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { TFunction } from 'i18next'
import {
  useListDocuments,
  useUploadDocument,
  useDeleteDocument,
  getListDocumentsQueryKey,
} from '@/shared/api/generated/documents/documents'
import type { Document, DocumentStatus } from '@/shared/api/generated/models'
import { useQueryClient } from '@tanstack/react-query'

function formatFileSize(bytes: number, t: TFunction): string {
  if (bytes === 0) return `0 ${t('common.units.byte')}`
  const k = 1024
  const sizes = [
    t('common.units.byte'),
    t('common.units.kilobyte'),
    t('common.units.megabyte'),
    t('common.units.gigabyte'),
  ]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

type StatusIconProps = Readonly<{ status: DocumentStatus }>

function StatusIcon({ status }: StatusIconProps) {
  switch (status) {
    case 'pending':
      return <Clock className="h-4 w-4 animate-pulse text-yellow-500" />
    case 'ingested':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    case 'error':
      return <AlertCircle className="h-4 w-4 text-destructive" />
  }
}

type DocumentItemProps = Readonly<{
  document: Document
  formatSize: (bytes: number) => string
  removeLabel: string
  onRemove: (documentId: string) => void
}>

function DocumentItem({
  document,
  formatSize,
  removeLabel,
  onRemove,
}: DocumentItemProps) {
  return (
    <div className="group flex items-center gap-3 rounded-md border bg-card p-3">
      <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{document.name}</p>
        <p className="text-xs text-muted-foreground">
          {formatSize(document.size)}
        </p>
      </div>
      <StatusIcon status={document.status} />
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
        onClick={() => onRemove(document.id)}
      >
        <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
        <span className="sr-only">{removeLabel}</span>
      </Button>
    </div>
  )
}

export function DocumentSidebar() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { documentSidebarOpen, setDocumentSidebarOpen } = useUIStore()
  const formatSize = (bytes: number) => formatFileSize(bytes, t)

  const documentsQuery = useListDocuments()
  const documents = documentsQuery.data?.data.items ?? []
  const hasPending = documents.some((d) => d.status === 'pending')

  // Poll while any document is pending
  React.useEffect(() => {
    if (!hasPending) return
    const interval = setInterval(() => {
      void queryClient.invalidateQueries({
        queryKey: getListDocumentsQueryKey(),
      })
    }, 3000)
    return () => clearInterval(interval)
  }, [hasPending, queryClient])

  const uploadMutation = useUploadDocument({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListDocumentsQueryKey(),
        })
      },
    },
  })

  const deleteMutation = useDeleteDocument({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListDocumentsQueryKey(),
        })
      },
    },
  })

  const handleFilesAdded = (files: File[]) => {
    files.forEach((file) => {
      uploadMutation.mutate({ data: { file } })
    })
  }

  const handleRemove = (documentId: string) => {
    deleteMutation.mutate({ documentId })
  }

  if (!documentSidebarOpen) return null

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <span className="text-sm font-semibold">{t('document.title')}</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setDocumentSidebarOpen(false)}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">{t('common.close')}</span>
        </Button>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden p-4">
        {documentsQuery.isLoading && (
          <div className="mb-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full rounded-md" />
            ))}
          </div>
        )}

        {!documentsQuery.isLoading && documents.length > 0 && (
          <div className="mb-4 shrink-0 space-y-2">
            <h3 className="text-sm font-medium text-muted-foreground">
              {t('document.addedDocuments')} ({documents.length})
            </h3>
            <div className="space-y-2 overflow-y-auto">
              {documents.map((doc) => (
                <DocumentItem
                  key={doc.id}
                  document={doc}
                  formatSize={formatSize}
                  removeLabel={t('document.removeDocument')}
                  onRemove={handleRemove}
                />
              ))}
            </div>
          </div>
        )}

        {uploadMutation.isPending && (
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('common.loading')}
          </div>
        )}

        <div
          className={cn(
            'flex min-h-0 flex-1 flex-col',
            documents.length > 0 && 'mt-4'
          )}
        >
          <h3 className="mb-2 shrink-0 text-sm font-medium text-muted-foreground">
            {t('document.uploadNew')}
          </h3>
          <Dropzone
            onFilesAdded={handleFilesAdded}
            accept=".pdf,.doc,.docx,.txt,.md"
            className="flex-1"
            labels={{
              idle: t('document.dropzoneIdle'),
              active: t('document.dropzoneActive'),
              accepted: t('document.dropzoneAccepted'),
            }}
          />
        </div>
      </div>
    </div>
  )
}
