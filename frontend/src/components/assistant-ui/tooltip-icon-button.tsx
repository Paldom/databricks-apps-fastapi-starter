import type { ComponentProps } from 'react'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'

export type TooltipIconButtonProps = Readonly<
  ComponentProps<typeof Button> & {
    tooltip: string
    side?: 'top' | 'bottom' | 'left' | 'right'
  }
>

export function TooltipIconButton({
  children,
  tooltip,
  side = 'bottom',
  variant = 'ghost',
  size = 'icon-xs',
  ...rest
}: TooltipIconButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant={variant} size={size} {...rest}>
          {children}
          <span className="sr-only">{tooltip}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent side={side}>{tooltip}</TooltipContent>
    </Tooltip>
  )
}
