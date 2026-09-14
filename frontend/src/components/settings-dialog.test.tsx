import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { SettingsDialog } from './settings-dialog'
import { resetUIStore, createTestQueryClient } from '@/test/utils'
import { QueryClientProvider } from '@tanstack/react-query'

function renderDialog() {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsDialog />
    </QueryClientProvider>
  )
}

describe('SettingsDialog', () => {
  beforeEach(() => {
    resetUIStore({ settingsDialogOpen: true })
  })

  it('renders the general section by default', () => {
    renderDialog()

    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'General' })).toBeInTheDocument()
    expect(screen.getByText('Theme')).toBeInTheDocument()
  })

  it('switches between sections via the nav', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))
    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /notifications/i }))
    expect(
      screen.getByRole('heading', { name: 'Notifications' })
    ).toBeInTheDocument()
  })

  it('loads profile data from server', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    expect(screen.getByDisplayValue('john@example.com')).toBeInTheDocument()
  })

  it('save button is disabled when form is clean', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeDisabled()
  })

  it('enables save when form is dirty', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Jane Doe')

    const saveButton = screen.getByRole('button', { name: 'Save' })
    expect(saveButton).toBeEnabled()
  })

  it('shows validation error for empty name', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Name')
    await user.clear(nameInput)

    // Type something in email to make form dirty
    const emailInput = screen.getByLabelText('Email')
    await user.clear(emailInput)
    await user.type(emailInput, 'new@example.com')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(screen.getByText('Name is required')).toBeInTheDocument()
  })

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    const emailInput = screen.getByLabelText('Email')
    await user.clear(emailInput)
    await user.type(emailInput, 'invalid')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(
      screen.getByText('Please enter a valid email address')
    ).toBeInTheDocument()
  })

  it('saves settings and shows success message', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    await waitFor(() => {
      expect(screen.getByDisplayValue('John Doe')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Jane Doe')

    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(
        screen.getByText('Settings saved successfully.')
      ).toBeInTheDocument()
    })
  })

  it('cancel button is disabled when form is clean', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /profile/i }))

    // Wait for the name input to appear with any value
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })

    // Wait for data to load into the form
    const nameInput = await screen.findByLabelText('Name')
    await waitFor(() => {
      expect((nameInput as HTMLInputElement).value).not.toBe('')
    })

    const cancelButton = screen.getByRole('button', { name: 'Cancel' })
    expect(cancelButton).toBeDisabled()
  })

  it('loads and toggles notifications', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Enable notifications')).toBeInTheDocument()
    })

    const toggle = screen.getByRole('switch')
    expect(toggle).toBeChecked()

    await user.click(toggle)

    // Toggle should now be unchecked
    expect(toggle).not.toBeChecked()
  })

  it('shows notifications section with switch', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: /notifications/i }))

    await waitFor(() => {
      expect(screen.getByRole('switch')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Receive notifications about updates and messages.')
    ).toBeInTheDocument()
  })
})
