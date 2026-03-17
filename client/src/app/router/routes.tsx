import { createBrowserRouter } from 'react-router-dom'
import { ChatShell } from '@/components/chat-shell'
import { AppRouteError } from '@/components/app-route-error'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <ChatShell />,
    errorElement: <AppRouteError />,
  },
])
