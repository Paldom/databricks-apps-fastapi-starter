import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from './dropdown-menu'

describe('ui/dropdown-menu', () => {
  it('renders menu content, submenus, and items', () => {
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Open</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Actions</DropdownMenuLabel>
          <DropdownMenuGroup>
            <DropdownMenuItem>
              New
              <DropdownMenuShortcut>⌘N</DropdownMenuShortcut>
            </DropdownMenuItem>
            <DropdownMenuCheckboxItem checked>Checked</DropdownMenuCheckboxItem>
            <DropdownMenuRadioGroup value="one">
              <DropdownMenuRadioItem value="one">One</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuSub open>
            <DropdownMenuSubTrigger>More</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem>Sub item</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>
    )

    expect(screen.getByText('Actions')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-label'
    )
    expect(screen.getByText('New')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-item'
    )
    expect(screen.getByText('Checked')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-checkbox-item'
    )
    expect(screen.getByText('One')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-radio-item'
    )
    expect(screen.getByText('More')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-sub-trigger'
    )
    expect(screen.getByText('Sub item')).toHaveAttribute(
      'data-slot',
      'dropdown-menu-item'
    )
  })
})
