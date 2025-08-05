'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { ServiceStatusBadge } from './service-status-badge'
import type { ServiceInstance } from '@/types/service'
import { cn } from '@/lib/utils'
import { useRelativeTime } from '@/hooks/use-relative-time'

interface ServiceInstanceCardProps {
  instance: ServiceInstance
  className?: string
}

export function ServiceInstanceCard({ instance, className }: ServiceInstanceCardProps) {
  const router = useRouter()

  // Support both snake_case and camelCase
  const serviceName = instance.service_name || instance.serviceName || ''
  const instanceId = instance.instance_id || instance.instanceId || ''
  const lastHeartbeat = instance.last_heartbeat || instance.lastHeartbeat || ''

  // Use the hook for real-time updates
  const relativeTime = useRelativeTime(lastHeartbeat)

  const handleClick = () => {
    router.push(`/services/${instanceId}`)
  }

  return (
    <div
      className={cn(
        'bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer',
        className
      )}
      onClick={handleClick}
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{serviceName}</h3>
        <ServiceStatusBadge status={instance.status} />
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center text-gray-600">
          <span className="w-24">Instance ID:</span>
          <span className="font-mono">{instanceId}</span>
        </div>
        <div className="flex items-center text-gray-600">
          <span className="w-24">Version:</span>
          <span className="font-mono">{instance.version}</span>
        </div>
        <div className="flex items-center text-gray-600">
          <span className="w-24">Last Heartbeat:</span>
          <span>{relativeTime}</span>
        </div>
      </div>
    </div>
  )
}
