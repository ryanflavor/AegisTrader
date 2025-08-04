/**
 * Repository for system status operations
 *
 * This module implements the repository pattern for system status,
 * providing a clean abstraction over data access with proper type safety.
 */

import { apiClient } from '@/lib/api-client';

/**
 * System status response
 */
export interface SystemStatus {
  timestamp: string;
  uptime_seconds: number;
  environment: string;
  connected_services: number;
  deployment_version: string;
}

/**
 * Health status response
 */
export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  nats_url: string;
}

/**
 * Type guard for SystemStatus
 */
export function isSystemStatus(value: unknown): value is SystemStatus {
  if (!value || typeof value !== 'object') return false;

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.timestamp === 'string' &&
    typeof obj.uptime_seconds === 'number' &&
    typeof obj.environment === 'string' &&
    typeof obj.connected_services === 'number' &&
    typeof obj.deployment_version === 'string'
  );
}

/**
 * Type guard for HealthStatus
 */
export function isHealthStatus(value: unknown): value is HealthStatus {
  if (!value || typeof value !== 'object') return false;

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.status === 'string' &&
    typeof obj.service === 'string' &&
    typeof obj.version === 'string' &&
    typeof obj.nats_url === 'string'
  );
}

/**
 * Repository interface for system operations
 */
export interface SystemRepositoryPort {
  getHealthStatus(): Promise<HealthStatus>;
  getSystemStatus(): Promise<SystemStatus>;
}

/**
 * HTTP implementation of the system repository
 */
export class SystemRepository implements SystemRepositoryPort {
  /**
   * Get health status
   */
  async getHealthStatus(): Promise<HealthStatus> {
    const response = await apiClient.get<unknown>('/health');

    if (!isHealthStatus(response)) {
      throw new Error('Invalid response format for health status');
    }

    return response;
  }

  /**
   * Get system status
   */
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await apiClient.get<unknown>('/status');

    if (!isSystemStatus(response)) {
      throw new Error('Invalid response format for system status');
    }

    return response;
  }
}

/**
 * Create a singleton instance of the repository
 */
export const systemRepository = new SystemRepository();
