import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from './breadcrumb'

describe('ui/breadcrumb', () => {
  it('renders breadcrumb structure and separators', () => {
    render(
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/home">Home</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Current</BreadcrumbPage>
          </BreadcrumbItem>
          <BreadcrumbEllipsis />
        </BreadcrumbList>
      </Breadcrumb>
    )

    expect(screen.getByLabelText('breadcrumb')).toBeInTheDocument()
    expect(screen.getByText('Home')).toHaveAttribute(
      'data-slot',
      'breadcrumb-link'
    )
    expect(screen.getByText('Current')).toHaveAttribute(
      'data-slot',
      'breadcrumb-page'
    )
    expect(screen.getByText('More')).toBeInTheDocument()
  })
})
