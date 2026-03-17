import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog'

describe('ui/dialog', () => {
  it('renders dialog content with header and footer', () => {
    render(
      <Dialog open>
        <DialogTrigger>Open</DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Title</DialogTitle>
            <DialogDescription>Description</DialogDescription>
          </DialogHeader>
          <DialogFooter showCloseButton>
            <button type="button">Save</button>
          </DialogFooter>
          <DialogClose>Dismiss</DialogClose>
        </DialogContent>
      </Dialog>
    )

    expect(screen.getByText('Title')).toHaveAttribute(
      'data-slot',
      'dialog-title'
    )
    expect(screen.getByText('Description')).toHaveAttribute(
      'data-slot',
      'dialog-description'
    )
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(
      screen.getAllByRole('button', { name: 'Close' }).length
    ).toBeGreaterThan(0)
    expect(screen.getByText('Dismiss')).toHaveAttribute(
      'data-slot',
      'dialog-close'
    )
  })

  it('can hide the close button in dialog content', () => {
    render(
      <Dialog open>
        <DialogContent showCloseButton={false}>
          <p>Body</p>
        </DialogContent>
      </Dialog>
    )

    expect(screen.queryByText('Close')).not.toBeInTheDocument()
    expect(screen.getByText('Body')).toBeInTheDocument()
  })
})
