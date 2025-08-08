/**
 * Repository for service instance operations
 *
 * This module implements the repository pattern for service instances,
 * providing a clean abstraction over data access with proper type safety.
 */

import { apiClient } from '@/lib/api-client';
import {
  ServiceInstance,
  HealthSummary,
  isServiceInstanceArray,
  isServiceInstance,
  isHealthSummary,
  ServiceStatus,
} from '@/types/service';

/**
 * Repository interface for service instance operations
 */
export interface ServiceInstanceRepositoryPort {
  getAllInstances(): Promise<ServiceInstance[]>;
  getInstancesByService(serviceName: string): Promise<ServiceInstance[]>;
  getInstance(serviceName: string, instanceId: string): Promise<ServiceInstance>;
  getInstancesByStatus(status: ServiceStatus): Promise<ServiceInstance[]>;
  getHealthSummary(): Promise<HealthSummary>;
}

/**
 * HTTP implementation of the service instance repository
 */
export class ServiceInstanceRepository implements ServiceInstanceRepositoryPort {
  /**
   * Transform API response to match frontend expectations
   */
  private transformInstance(instance: any): ServiceInstance {
    // Always use the actual values from API (which are in camelCase)
    const serviceName = instance.serviceName || instance.service_name || '';
    const instanceId = instance.instanceId || instance.instance_id || '';
    const lastHeartbeat = instance.lastHeartbeat || instance.last_heartbeat || '';
    const stickyActiveGroup = instance.stickyActiveGroup || instance.sticky_active_group || null;

    return {
      // Snake case for compatibility with existing code
      service_name: serviceName,
      instance_id: instanceId,
      version: instance.version,
      status: instance.status,
      last_heartbeat: lastHeartbeat,
      sticky_active_group: stickyActiveGroup,
      metadata: instance.metadata,
      // Keep camelCase versions for compatibility
      serviceName: serviceName,
      instanceId: instanceId,
      lastHeartbeat: lastHeartbeat,
      stickyActiveGroup: stickyActiveGroup,
    };
  }

  /**
   * Get all service instances
   */
  async getAllInstances(): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>('/instances');

    if (!Array.isArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    // Transform and sort by service name and instance ID for stable ordering
    return response
      .map(instance => this.transformInstance(instance))
      .sort((a, b) => {
        // First sort by service name
        const serviceCompare = (a.service_name || '').localeCompare(b.service_name || '');
        if (serviceCompare !== 0) return serviceCompare;

        // Then sort by instance ID for stable ordering within same service
        return (a.instance_id || '').localeCompare(b.instance_id || '');
      });
  }

  /**
   * Get instances for a specific service
   */
  async getInstancesByService(serviceName: string): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>(`/instances/${serviceName}`);

    if (!Array.isArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    // Transform and sort by instance ID for stable ordering
    return response
      .map(instance => this.transformInstance(instance))
      .sort((a, b) => (a.instance_id || '').localeCompare(b.instance_id || ''));
  }

  /**
   * Get a specific service instance
   */
  async getInstance(serviceName: string, instanceId: string): Promise<ServiceInstance> {
    const response = await apiClient.get<unknown>(
      `/instances/${serviceName}/${instanceId}`
    );

    if (!response || typeof response !== 'object') {
      throw new Error('Invalid response format for service instance');
    }

    return this.transformInstance(response);
  }

  /**
   * Get instances by status
   */
  async getInstancesByStatus(status: ServiceStatus): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>(`/instances/status/${status}`);

    if (!Array.isArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    // Transform and sort for stable ordering
    return response
      .map(instance => this.transformInstance(instance))
      .sort((a, b) => {
        // First sort by service name
        const serviceCompare = (a.service_name || '').localeCompare(b.service_name || '');
        if (serviceCompare !== 0) return serviceCompare;

        // Then sort by instance ID
        return (a.instance_id || '').localeCompare(b.instance_id || '');
      });
  }

  /**
   * Get health summary
   */
  async getHealthSummary(): Promise<HealthSummary> {
    const response = await apiClient.get<unknown>('/instances/health/summary');

    if (!isHealthSummary(response)) {
      throw new Error('Invalid response format for health summary');
    }

    return response;
  }
}

/**
 * Create a singleton instance of the repository
 */
export const serviceInstanceRepository = new ServiceInstanceRepository();
