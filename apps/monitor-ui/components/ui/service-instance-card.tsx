'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { ServiceStatusBadge } from './service-status-badge'
import type { ServiceInstance } from '@/types/service'
import { cn } from '@/lib/utils'

interface ServiceInstanceCardProps {
  instance: ServiceInstance
  className?: string
}

export function ServiceInstanceCard({ instance, className }: ServiceInstanceCardProps) {
  const router = useRouter()

  const formatLastHeartbeat = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)

    if (diffSecs < 60) return `${diffSecs}s ago`
    const diffMins = Math.floor(diffSecs / 60)
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    return `${diffHours}h ago`
  }

  const handleClick = () => {
    router.push(`/services/${instance.instance_id}`)
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
        <h3 className="text-lg font-semibold text-gray-800">{instance.service_name}</h3>
        <ServiceStatusBadge status={instance.status} />
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center text-gray-600">
          <span className="w-24">Instance ID:</span>
          <span className="font-mono">{instance.instance_id}</span>
        </div>
        <div className="flex items-center text-gray-600">
          <span className="w-24">Version:</span>
          <span className="font-mono">{instance.version}</span>
        </div>
        <div className="flex items-center text-gray-600">
          <span className="w-24">Last Heartbeat:</span>
          <span>{formatLastHeartbeat(instance.last_heartbeat)}</span>
        </div>
      </div>
    </div>
  )
}
