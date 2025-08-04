'use client'

import { ServiceInstanceCard } from '@/components/ui/service-instance-card'
import { useServiceInstances } from '@/hooks/use-service-instances'
import { useSystemStatus } from '@/hooks/use-system-status'

export default function Home() {
  // Use custom hooks for data fetching with automatic polling
  const {
    instances: serviceInstances,
    loading: instancesLoading,
    error: instancesError,
  } = useServiceInstances();

  const {
    systemStatus,
    healthStatus,
    loading: statusLoading,
    error: statusError,
  } = useSystemStatus();

  // Combine loading states
  const loading = instancesLoading || statusLoading;
  const error = instancesError || statusError;

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    return `${hours}h ${minutes}m ${secs}s`
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-800">AegisSDK 服务监控</h1>
          <p className="mt-2 text-lg text-gray-600">Real-time monitoring dashboard for the AegisTrader system</p>
        </header>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-gray-600">Loading system information...</p>
          </div>
        ) : error ? (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <p className="font-bold">Error</p>
            <p>{error.message}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Health Status Card */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">Health Status</h2>
              {healthStatus && (
                <div className="space-y-3">
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Status:</span>
                    <span className={`font-semibold ${healthStatus.status === 'healthy' ? 'text-green-600' : 'text-red-600'}`}>
                      {healthStatus.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Service:</span>
                    <span className="font-mono">{healthStatus.service}</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Version:</span>
                    <span className="font-mono">{healthStatus.version}</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">NATS URL:</span>
                    <span className="font-mono text-sm">{healthStatus.nats_url}</span>
                  </div>
                </div>
              )}
            </div>

            {/* System Status Card */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">System Status</h2>
              {systemStatus && (
                <div className="space-y-3">
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Environment:</span>
                    <span className="font-semibold">{systemStatus.environment}</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Uptime:</span>
                    <span className="font-mono">{formatUptime(systemStatus.uptime_seconds)}</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Version:</span>
                    <span className="font-mono">{systemStatus.deployment_version}</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-gray-600 w-32">Services:</span>
                    <span>{systemStatus.connected_services} connected</span>
                  </div>
                </div>
              )}
            </div>

            {/* Timestamp */}
            <div className="md:col-span-2 text-center text-sm text-gray-500 mt-4">
              Last updated: {systemStatus ? new Date(systemStatus.timestamp).toLocaleString() : 'N/A'}
            </div>
          </div>
        )}

        {/* Service Instances Section */}
        <section className="mt-12">
          <h2 className="text-2xl font-semibold mb-6 text-gray-800">Service Instances</h2>
          {serviceInstances.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {serviceInstances.map((instance) => (
                <ServiceInstanceCard
                  key={`${instance.service_name}-${instance.instance_id}`}
                  instance={instance}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-md p-6 text-center text-gray-500">
              No service instances found
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
