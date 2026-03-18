import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from './select'

describe('ui/select', () => {
  it('renders select content and items', () => {
    render(
      <Select open value="a" onValueChange={() => {}}>
        <SelectTrigger size="sm">
          <SelectValue placeholder="Pick one" />
        </SelectTrigger>
        <SelectContent position="popper">
          <SelectGroup>
            <SelectLabel>Group</SelectLabel>
            <SelectItem value="a">Option A</SelectItem>
            <SelectSeparator />
            <SelectItem value="b">Option B</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    )

    expect(screen.getByText('Group')).toHaveAttribute(
      'data-slot',
      'select-label'
    )
    const optionA = screen
      .getAllByText('Option A')
      .find((node) => node.closest('[data-slot="select-item"]'))
    const optionB = screen
      .getAllByText('Option B')
      .find((node) => node.closest('[data-slot="select-item"]'))

    expect(optionA?.closest('[data-slot="select-item"]')).toBeTruthy()
    expect(optionB?.closest('[data-slot="select-item"]')).toBeTruthy()
  })
})
