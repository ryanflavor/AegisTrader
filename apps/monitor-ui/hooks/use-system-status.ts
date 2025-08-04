/**
 * Custom hook for managing system status data
 *
 * This hook provides a clean abstraction for components to access
 * system status data with automatic polling and error handling.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { systemRepository, SystemStatus, HealthStatus } from '@/repositories/system.repository';
import { ApiClientError } from '@/lib/api-client';

/**
 * Configuration options for the hook
 */
export interface UseSystemStatusOptions {
  /**
   * Polling interval in milliseconds (default: 5000)
   */
  pollingInterval?: number;
  /**
   * Whether to enable polling (default: true)
   */
  enablePolling?: boolean;
}

/**
 * Return type for the hook
 */
export interface UseSystemStatusResult {
  systemStatus: SystemStatus | null;
  healthStatus: HealthStatus | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching and managing system status
 */
export function useSystemStatus(
  options: UseSystemStatusOptions = {}
): UseSystemStatusResult {
  const {
    pollingInterval = 5000,
    enablePolling = true,
  } = options;

  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Use ref to store interval ID
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch function
  const fetchStatus = useCallback(async () => {
    try {
      setError(null);

      // Fetch both statuses in parallel
      const [health, system] = await Promise.all([
        systemRepository.getHealthStatus(),
        systemRepository.getSystemStatus(),
      ]);

      setHealthStatus(health);
      setSystemStatus(system);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(new Error(`Failed to fetch system status: ${err.message}`));
      } else if (err instanceof Error) {
        setError(err);
      } else {
        setError(new Error('An unknown error occurred'));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Refresh function
  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchStatus();
  }, [fetchStatus]);

  // Initial fetch and polling setup
  useEffect(() => {
    // Initial fetch
    fetchStatus();

    // Set up polling if enabled
    if (enablePolling) {
      intervalRef.current = setInterval(fetchStatus, pollingInterval);
    }

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchStatus, enablePolling, pollingInterval]);

  return {
    systemStatus,
    healthStatus,
    loading,
    error,
    refresh,
  };
}
