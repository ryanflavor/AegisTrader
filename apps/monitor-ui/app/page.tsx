'use client'

import { useEffect, useState } from 'react'

interface SystemStatus {
  timestamp: string
  uptime_seconds: number
  environment: string
  connected_services: number
  deployment_version: string
}

interface HealthStatus {
  status: string
  service: string
  version: string
  nats_url: string
}

export default function Home() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch health status
        const healthRes = await fetch('/api/proxy/health')
        if (healthRes.ok) {
          const health = await healthRes.json()
          setHealthStatus(health)
        }

        // Fetch system status
        const statusRes = await fetch('/api/proxy/status')
        if (statusRes.ok) {
          const status = await statusRes.json()
          setSystemStatus(status)
        }
      } catch (err) {
        setError('Failed to fetch system information')
        console.error('Error fetching data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    // Refresh data every 5 seconds
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    return `${hours}h ${minutes}m ${secs}s`
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-800">AegisTrader Monitor v2</h1>
          <p className="mt-2 text-lg text-gray-600">Real-time monitoring dashboard for the AegisTrader system (Updated)</p>
        </header>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p className="mt-2 text-gray-600">Loading system information...</p>
          </div>
        ) : error ? (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <p className="font-bold">Error</p>
            <p>{error}</p>
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
      </div>
    </main>
  )
}