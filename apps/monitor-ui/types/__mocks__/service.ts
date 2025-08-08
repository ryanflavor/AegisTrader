// Mock implementations for service types
export const ServiceStatusValues = {
  ACTIVE: 'ACTIVE',
  UNHEALTHY: 'UNHEALTHY',
  STANDBY: 'STANDBY',
} as const;

export type ServiceStatus = keyof typeof ServiceStatusValues;

export interface ServiceInstance {
  service_name: string;
  instance_id: string;
  version: string;
  status: ServiceStatus;
  last_heartbeat: string;
  sticky_active_group?: string | null;
  metadata?: Record<string, unknown>;
  serviceName?: string;
  instanceId?: string;
  lastHeartbeat?: string;
  stickyActiveGroup?: string | null;
}

export interface HealthSummary {
  total: number;
  active: number;
  unhealthy: number;
  standby: number;
}

export interface ApiError {
  detail: string;
  status?: number;
}

// Mock type guards - always return true in tests
export const isServiceInstance = jest.fn((value: unknown): value is ServiceInstance => {
  if (!value || typeof value !== 'object') return false;
  const obj = value as any;
  return !!(obj.service_name || obj.serviceName);
});

export const isServiceInstanceArray = jest.fn((value: unknown): value is ServiceInstance[] => {
  return Array.isArray(value);
});

export const isHealthSummary = jest.fn((value: unknown): value is HealthSummary => {
  if (!value || typeof value !== 'object') return false;
  const obj = value as any;
  return typeof obj.total === 'number';
});

export const isApiError = jest.fn((value: unknown): value is ApiError => {
  if (!value || typeof value !== 'object') return false;
  const obj = value as any;
  return typeof obj.detail === 'string';
});
