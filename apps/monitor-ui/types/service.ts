/**
 * Service instance status types
 */
export const ServiceStatusValues = {
  ACTIVE: 'ACTIVE',
  UNHEALTHY: 'UNHEALTHY',
  STANDBY: 'STANDBY',
} as const;

export type ServiceStatus = keyof typeof ServiceStatusValues;

/**
 * Domain model for a running service instance
 */
export interface ServiceInstance {
  service_name: string;
  instance_id: string;
  version: string;
  status: ServiceStatus;
  last_heartbeat: string;
  sticky_active_group?: string | null;
  metadata?: Record<string, unknown>;
}

/**
 * Health summary across all services
 */
export interface HealthSummary {
  total: number;
  active: number;
  unhealthy: number;
  standby: number;
}

/**
 * API error response
 */
export interface ApiError {
  detail: string;
  status?: number;
}

/**
 * Type guard to check if a value is a ServiceInstance
 */
export function isServiceInstance(value: unknown): value is ServiceInstance {
  if (!value || typeof value !== 'object') return false;

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.service_name === 'string' &&
    typeof obj.instance_id === 'string' &&
    typeof obj.version === 'string' &&
    Object.values(ServiceStatusValues).includes(obj.status as string) &&
    typeof obj.last_heartbeat === 'string'
  );
}

/**
 * Type guard to check if a value is an array of ServiceInstances
 */
export function isServiceInstanceArray(value: unknown): value is ServiceInstance[] {
  return Array.isArray(value) && value.every(isServiceInstance);
}

/**
 * Type guard to check if a value is a HealthSummary
 */
export function isHealthSummary(value: unknown): value is HealthSummary {
  if (!value || typeof value !== 'object') return false;

  const obj = value as Record<string, unknown>;

  return (
    typeof obj.total === 'number' &&
    typeof obj.active === 'number' &&
    typeof obj.unhealthy === 'number' &&
    typeof obj.standby === 'number'
  );
}

/**
 * Type guard to check if a value is an ApiError
 */
export function isApiError(value: unknown): value is ApiError {
  if (!value || typeof value !== 'object') return false;

  const obj = value as Record<string, unknown>;

  return typeof obj.detail === 'string';
}
