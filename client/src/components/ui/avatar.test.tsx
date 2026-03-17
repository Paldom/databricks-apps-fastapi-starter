import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  Avatar,
  AvatarBadge,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
  AvatarImage,
} from './avatar'

describe('ui/avatar', () => {
  it('renders avatar variants and group utilities', () => {
    render(
      <AvatarGroup>
        <Avatar size="sm">
          <AvatarImage src="/avatar.png" alt="User avatar" />
          <AvatarFallback>AB</AvatarFallback>
          <AvatarBadge>!</AvatarBadge>
        </Avatar>
        <AvatarGroupCount>+2</AvatarGroupCount>
      </AvatarGroup>
    )

    const avatar = screen.getByText('AB').closest('[data-slot="avatar"]')
    expect(avatar).toHaveAttribute('data-size', 'sm')
    expect(screen.getByText('AB')).toHaveAttribute(
      'data-slot',
      'avatar-fallback'
    )
    expect(screen.getByText('!')).toHaveAttribute('data-slot', 'avatar-badge')
    expect(screen.getByText('+2')).toHaveAttribute(
      'data-slot',
      'avatar-group-count'
    )
  })
})
