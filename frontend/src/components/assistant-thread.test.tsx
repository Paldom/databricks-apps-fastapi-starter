import {
  AssistantRuntimeProvider,
  useLocalRuntime,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssistantThread } from './assistant-thread'

function ThreadFixture({ message }: Readonly<{ message: ThreadMessageLike }>) {
  const runtime = useLocalRuntime(
    { run: () => Promise.resolve({ content: [] }) },
    { initialMessages: [message] }
  )
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantThread />
    </AssistantRuntimeProvider>
  )
}

it('renders knowledge sources, Genie text and SQL, and collapsed fallback details', async () => {
  render(
    <ThreadFixture
      message={{
        role: 'assistant',
        content: [
          {
            type: 'tool-call',
            toolCallId: 'k',
            toolName: 'knowledge_assistant',
            args: {},
            argsText: '{}',
            result: '[1] First source\n[2] Second source',
          },
          {
            type: 'tool-call',
            toolCallId: 'g',
            toolName: 'genie',
            args: {},
            argsText: '{}',
            result: { text: 'Sales: 42', sql: 'SELECT 42' },
          },
          {
            type: 'tool-call',
            toolCallId: 'f',
            toolName: 'other_tool',
            args: { q: 'query' },
            argsText: '{"q":"query"}',
            result: 'Other result',
          },
        ],
      }}
    />
  )
  expect(
    await screen.findByRole('heading', { name: 'Sources' })
  ).toBeInTheDocument()
  expect(screen.getAllByRole('listitem')).toHaveLength(2)
  expect(screen.getByText('Sales: 42').tagName).toBe('PRE')
  expect(screen.getByText('SELECT 42').tagName).toBe('PRE')
  const summary = screen.getByText('other_tool')
  expect(summary.closest('details')).not.toHaveAttribute('open')
  await userEvent.click(summary)
  expect(summary.closest('details')).toHaveAttribute('open')
  expect(screen.getByText('{"q":"query"}')).toBeVisible()
  expect(screen.getByText('Other result')).toBeVisible()
})

it('shows runtime errors with their trace id inline', () => {
  render(
    <ThreadFixture
      message={{
        role: 'assistant',
        content: [],
        status: {
          type: 'incomplete',
          reason: 'error',
          error: 'Request failed (trace trace-123)',
        },
      }}
    />
  )
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Request failed (trace trace-123)'
  )
})
