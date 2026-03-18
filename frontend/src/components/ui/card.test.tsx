import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from './card'

describe('ui/card', () => {
  it('renders card structure with slots', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardAction>Action</CardAction>
          <CardDescription>Description</CardDescription>
        </CardHeader>
        <CardContent>Body</CardContent>
        <CardFooter>Footer</CardFooter>
      </Card>
    )

    const cardTitle = screen.getByText('Title')
    expect(cardTitle).toHaveAttribute('data-slot', 'card-title')
    expect(screen.getByText('Description')).toHaveAttribute(
      'data-slot',
      'card-description'
    )
    expect(screen.getByText('Body')).toHaveAttribute(
      'data-slot',
      'card-content'
    )
    expect(screen.getByText('Footer')).toHaveAttribute(
      'data-slot',
      'card-footer'
    )

    const card = cardTitle.closest('[data-slot="card"]')
    expect(card?.className).toContain('rounded-xl')
    expect(screen.getByText('Action').className).toContain('col-start-2')
  })
})
