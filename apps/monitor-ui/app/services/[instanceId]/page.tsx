'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ServiceStatusBadge } from '@/components/ui/service-status-badge'
import { serviceInstanceRepository } from '@/repositories/service-instance.repository'
import type { ServiceInstance } from '@/types/service'
import { ApiClientError } from '@/lib/api-client'

interface TabProps {
  label: string
  isActive: boolean
  onClick: () => void
}

function Tab({ label, isActive, onClick }: TabProps) {
  return (
    <button
      className={`px-6 py-3 font-medium transition-colors ${
        isActive
          ? 'text-blue-600 border-b-2 border-blue-600'
          : 'text-gray-600 hover:text-gray-800'
      }`}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

export default function ServiceDetailPage() {
  const params = useParams()
  const router = useRouter()
  const instanceId = params.instanceId as string

  const [instance, setInstance] = useState<ServiceInstance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [activeTab, setActiveTab] = useState('metrics')

  const fetchInstance = useCallback(async () => {
    try {
      setError(null)

      // First, fetch all instances to find the one we need
      const instances = await serviceInstanceRepository.getAllInstances()
      const foundInstance = instances.find(inst => inst.instance_id === instanceId)

      if (!foundInstance) {
        setError(new Error('Instance not found'))
      } else {
        setInstance(foundInstance)
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(new Error(`Failed to fetch instance: ${err.message}`))
      } else if (err instanceof Error) {
        setError(err)
      } else {
        setError(new Error('Failed to fetch instance details'))
      }
      console.error('Error fetching instance:', err)
    } finally {
      setLoading(false)
    }
  }, [instanceId])

  useEffect(() => {
    // Initial fetch
    fetchInstance()

    // Set up polling
    const interval = setInterval(fetchInstance, 5000)

    // Cleanup
    return () => clearInterval(interval)
  }, [fetchInstance])

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-gray-600">Loading instance details...</p>
          </div>
        </div>
      </main>
    )
  }

  if (error || !instance) {
    return (
      <main className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <p className="font-bold">Error</p>
            <p>{error?.message || 'Instance not found'}</p>
          </div>
          <button
            onClick={() => router.push('/')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </main>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/')}
            className="mb-4 text-blue-600 hover:text-blue-800"
          >
            ← Back to Dashboard
          </button>

          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h1 className="text-3xl font-bold text-gray-800">{instance.service_name}</h1>
                <p className="text-gray-600 mt-1">Instance: {instance.instance_id}</p>
              </div>
              <ServiceStatusBadge status={instance.status} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Version:</span>
                <p className="font-mono">{instance.version}</p>
              </div>
              <div>
                <span className="text-gray-500">Last Heartbeat:</span>
                <p>{formatTimestamp(instance.last_heartbeat)}</p>
              </div>
              {instance.sticky_active_group && (
                <div>
                  <span className="text-gray-500">Sticky Group:</span>
                  <p>{instance.sticky_active_group}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow-md">
          <div className="border-b border-gray-200">
            <div className="flex space-x-8 px-6">
              <Tab
                label="Performance Metrics"
                isActive={activeTab === 'metrics'}
                onClick={() => setActiveTab('metrics')}
              />
              <Tab
                label="Configuration"
                isActive={activeTab === 'config'}
                onClick={() => setActiveTab('config')}
              />
              <Tab
                label="Logs/Events"
                isActive={activeTab === 'logs'}
                onClick={() => setActiveTab('logs')}
              />
            </div>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'metrics' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Performance Metrics</h2>
                <div className="bg-gray-100 rounded p-4 text-gray-600">
                  <p>Performance metrics visualization will be implemented here.</p>
                  <p className="mt-2">This will include:</p>
                  <ul className="list-disc list-inside mt-2">
                    <li>RPC Latency trends</li>
                    <li>Success/Error rates</li>
                    <li>Queue depth metrics</li>
                  </ul>
                </div>
              </div>
            )}

            {activeTab === 'config' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Configuration</h2>
                {instance.metadata && Object.keys(instance.metadata).length > 0 ? (
                  <div className="bg-gray-50 rounded p-4">
                    <pre className="font-mono text-sm">
                      {JSON.stringify(instance.metadata, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <p className="text-gray-600">No configuration metadata available</p>
                )}
              </div>
            )}

            {activeTab === 'logs' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Logs & Events</h2>
                <div className="bg-gray-100 rounded p-4 text-gray-600">
                  <p>Recent logs and events will be displayed here.</p>
                  <p className="mt-2">This will show critical events and log entries for this instance.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
