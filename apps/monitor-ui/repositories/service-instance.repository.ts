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
   * Get all service instances
   */
  async getAllInstances(): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>('/instances');

    if (!isServiceInstanceArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    return response;
  }

  /**
   * Get instances for a specific service
   */
  async getInstancesByService(serviceName: string): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>(`/instances/${serviceName}`);

    if (!isServiceInstanceArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    return response;
  }

  /**
   * Get a specific service instance
   */
  async getInstance(serviceName: string, instanceId: string): Promise<ServiceInstance> {
    const response = await apiClient.get<unknown>(
      `/instances/${serviceName}/${instanceId}`
    );

    if (!isServiceInstance(response)) {
      throw new Error('Invalid response format for service instance');
    }

    return response;
  }

  /**
   * Get instances by status
   */
  async getInstancesByStatus(status: ServiceStatus): Promise<ServiceInstance[]> {
    const response = await apiClient.get<unknown>(`/instances/status/${status}`);

    if (!isServiceInstanceArray(response)) {
      throw new Error('Invalid response format for service instances');
    }

    return response;
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
