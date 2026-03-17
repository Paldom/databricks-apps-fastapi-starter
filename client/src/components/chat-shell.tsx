import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useUIStore } from '@/shared/store/ui'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable'
import { AppHeader } from './app-header'
import { AppSidebar } from './app-sidebar'
import { ChatSearchDialog } from './chat-search-dialog'
import { SettingsDialog } from './settings-dialog'
import { DocumentSidebar } from './document-sidebar'
import { AssistantThread } from './assistant-thread'
import { useChatRuntime } from '@/lib/assistant/use-chat-runtime'

export function ChatShell() {
  const { documentSidebarOpen } = useUIStore()
  const runtime = useChatRuntime()

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SidebarProvider defaultOpen>
        <AppSidebar />
        <SidebarInset className="flex flex-col overflow-hidden">
          <AppHeader />
          <ResizablePanelGroup orientation="horizontal" className="flex-1">
            <ResizablePanel
              defaultSize="70%"
              minSize={documentSidebarOpen ? '30%' : '100%'}
              className="min-w-0"
            >
              <AssistantThread className="h-full" />
            </ResizablePanel>
            {documentSidebarOpen && (
              <>
                <ResizableHandle withHandle />
                <ResizablePanel defaultSize="30%" minSize="20%" maxSize="60%">
                  <DocumentSidebar />
                </ResizablePanel>
              </>
            )}
          </ResizablePanelGroup>
        </SidebarInset>
        <ChatSearchDialog />
        <SettingsDialog />
      </SidebarProvider>
    </AssistantRuntimeProvider>
  )
}
