/**
 * Custom hook for managing service instance data
 *
 * This hook provides a clean abstraction for components to access
 * service instance data with automatic polling and error handling.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { serviceInstanceRepository } from '@/repositories/service-instance.repository';
import { ServiceInstance } from '@/types/service';
import { ApiClientError } from '@/lib/api-client';

/**
 * Configuration options for the hook
 */
export interface UseServiceInstancesOptions {
  /**
   * Polling interval in milliseconds (default: 5000)
   */
  pollingInterval?: number;
  /**
   * Whether to enable polling (default: true)
   */
  enablePolling?: boolean;
  /**
   * Service name to filter by (optional)
   */
  serviceName?: string;
}

/**
 * Return type for the hook
 */
export interface UseServiceInstancesResult {
  instances: ServiceInstance[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching and managing service instances
 */
export function useServiceInstances(
  options: UseServiceInstancesOptions = {}
): UseServiceInstancesResult {
  const {
    pollingInterval = 5000,
    enablePolling = true,
    serviceName,
  } = options;

  const [instances, setInstances] = useState<ServiceInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Use ref to store interval ID
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch function
  const fetchInstances = useCallback(async () => {
    try {
      setError(null);

      const data = serviceName
        ? await serviceInstanceRepository.getInstancesByService(serviceName)
        : await serviceInstanceRepository.getAllInstances();

      setInstances(data);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(new Error(`Failed to fetch instances: ${err.message}`));
      } else if (err instanceof Error) {
        setError(err);
      } else {
        setError(new Error('An unknown error occurred'));
      }
    } finally {
      setLoading(false);
    }
  }, [serviceName]);

  // Refresh function
  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchInstances();
  }, [fetchInstances]);

  // Initial fetch and polling setup
  useEffect(() => {
    // Initial fetch
    fetchInstances();

    // Set up polling if enabled
    if (enablePolling) {
      intervalRef.current = setInterval(fetchInstances, pollingInterval);
    }

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchInstances, enablePolling, pollingInterval]);

  return {
    instances,
    loading,
    error,
    refresh,
  };
}
