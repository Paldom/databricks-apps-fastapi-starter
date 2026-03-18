import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from './command'

describe('ui/command', () => {
  it('renders command palette primitives', () => {
    render(
      <>
        <Command>
          <CommandInput placeholder="Search..." />
          <CommandList>
            <CommandEmpty>No results</CommandEmpty>
          </CommandList>
        </Command>
        <Command>
          <CommandList>
            <CommandGroup heading="Group">
              <CommandItem>
                Action
                <CommandShortcut>⌘K</CommandShortcut>
              </CommandItem>
            </CommandGroup>
            <CommandSeparator />
          </CommandList>
        </Command>
      </>
    )

    expect(screen.getByPlaceholderText('Search...')).toHaveAttribute(
      'data-slot',
      'command-input'
    )
    expect(screen.getByText('No results')).toHaveAttribute(
      'data-slot',
      'command-empty'
    )
    expect(screen.getByText('Action')).toHaveAttribute(
      'data-slot',
      'command-item'
    )
    expect(screen.getByText('⌘K')).toHaveAttribute(
      'data-slot',
      'command-shortcut'
    )
  })
})
