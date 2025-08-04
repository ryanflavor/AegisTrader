import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const serviceStatusBadgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      status: {
        ACTIVE: 'bg-green-100 text-green-800',
        UNHEALTHY: 'bg-red-100 text-red-800',
        STANDBY: 'bg-gray-100 text-gray-800',
      },
    },
    defaultVariants: {
      status: 'STANDBY',
    },
  }
)

export interface ServiceStatusBadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof serviceStatusBadgeVariants> {
  status: 'ACTIVE' | 'UNHEALTHY' | 'STANDBY'
}

export function ServiceStatusBadge({
  className,
  status,
  ...props
}: ServiceStatusBadgeProps) {
  return (
    <div
      className={cn(serviceStatusBadgeVariants({ status }), className)}
      {...props}
    >
      {status}
    </div>
  )
}
