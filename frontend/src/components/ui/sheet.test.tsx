import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from './sheet'

describe('ui/sheet', () => {
  it.each(['right', 'left', 'top', 'bottom'] as const)(
    'renders sheet content on the %s side',
    (side) => {
      render(
        <Sheet open>
          <SheetTrigger>Open</SheetTrigger>
          <SheetContent side={side}>
            <SheetHeader>
              <SheetTitle>Title</SheetTitle>
              <SheetDescription>Description</SheetDescription>
            </SheetHeader>
            <SheetFooter>Footer</SheetFooter>
            <SheetClose>Dismiss</SheetClose>
          </SheetContent>
        </Sheet>
      )

      expect(screen.getByText('Title')).toBeInTheDocument()
      expect(screen.getByText('Dismiss')).toHaveAttribute(
        'data-slot',
        'sheet-close'
      )
    }
  )

  it('can hide the close button', () => {
    render(
      <Sheet open>
        <SheetContent showCloseButton={false}>
          <p>Body</p>
        </SheetContent>
      </Sheet>
    )

    expect(screen.queryByText('Close')).not.toBeInTheDocument()
    expect(screen.getByText('Body')).toBeInTheDocument()
  })
})
