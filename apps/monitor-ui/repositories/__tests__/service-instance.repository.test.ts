import { ServiceInstanceRepository } from '../service-instance.repository';
import { apiClient } from '../../lib/api-client';

// Mock apiClient
jest.mock('../../lib/api-client', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  }
}));

// Mock type guards
jest.mock('../../types/service', () => ({
  ...jest.requireActual('../../types/service'),
  isServiceInstance: jest.fn((value) => {
    if (!value || typeof value !== 'object') return false;
    const obj = value as any;
    return !!(obj.service_name && obj.instance_id);
  }),
  isServiceInstanceArray: jest.fn((value) => {
    return Array.isArray(value) && value.length > 0 && value[0].service_name;
  }),
  isHealthSummary: jest.fn((value) => {
    if (!value || typeof value !== 'object') return false;
    const obj = value as any;
    return typeof obj.total === 'number';
  }),
  isApiError: jest.fn((value) => {
    if (!value || typeof value !== 'object') return false;
    const obj = value as any;
    return typeof obj.detail === 'string';
  }),
}));

describe('ServiceInstanceRepository', () => {
  let repository: ServiceInstanceRepository;

  beforeEach(() => {
    repository = new ServiceInstanceRepository();
    jest.clearAllMocks();
  });

  describe('getAllInstances', () => {
    it('should fetch all service instances', async () => {
      const mockInstances = [
        {
          instance_id: '1',
          service_type: 'api',
          service_name: 'test-api',
          version: '1.0.0',
          status: 'running',
          metadata: {},
          last_heartbeat: '2024-01-01T00:00:00Z',
          registered_at: '2024-01-01T00:00:00Z',
        },
        {
          instance_id: '2',
          service_type: 'worker',
          service_name: 'test-worker',
          version: '1.0.0',
          status: 'running',
          metadata: {},
          last_heartbeat: '2024-01-01T00:00:00Z',
          registered_at: '2024-01-01T00:00:00Z',
        },
      ];

      (apiClient.get as jest.Mock).mockResolvedValue(mockInstances);

      const result = await repository.getAllInstances();

      expect(apiClient.get).toHaveBeenCalledWith('/instances');
      expect(result).toEqual(mockInstances);
    });

    it('should handle error when response format is invalid', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue('invalid response');

      await expect(repository.getAllInstances()).rejects.toThrow(
        'Invalid response format for service instances'
      );
    });
  });

  describe('getInstancesByService', () => {
    it('should fetch instances by service name', async () => {
      const mockInstances = [
        {
          instance_id: '1',
          service_type: 'api',
          service_name: 'test-api',
          version: '1.0.0',
          status: 'running',
          metadata: {},
          last_heartbeat: '2024-01-01T00:00:00Z',
          registered_at: '2024-01-01T00:00:00Z',
        },
      ];

      (apiClient.get as jest.Mock).mockResolvedValue(mockInstances);

      const result = await repository.getInstancesByService('test-api');

      expect(apiClient.get).toHaveBeenCalledWith('/instances/test-api');
      expect(result).toEqual(mockInstances);
    });

    it('should handle invalid response format', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue(null);

      await expect(repository.getInstancesByService('test-api')).rejects.toThrow(
        'Invalid response format for service instances'
      );
    });
  });

  describe('getInstance', () => {
    it('should fetch a specific service instance', async () => {
      const mockInstance = {
        instance_id: '1',
        service_type: 'api',
        service_name: 'test-api',
        version: '1.0.0',
        status: 'running',
        metadata: {},
        last_heartbeat: '2024-01-01T00:00:00Z',
        registered_at: '2024-01-01T00:00:00Z',
      };

      (apiClient.get as jest.Mock).mockResolvedValue(mockInstance);

      const result = await repository.getInstance('test-api', '1');

      expect(apiClient.get).toHaveBeenCalledWith('/instances/test-api/1');
      expect(result).toEqual(mockInstance);
    });

    it('should handle invalid response format', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue([]);

      await expect(repository.getInstance('test-api', '1')).rejects.toThrow(
        'Invalid response format for service instance'
      );
    });
  });

  describe('getInstancesByStatus', () => {
    it('should fetch instances by status', async () => {
      const mockInstances = [
        {
          instance_id: '1',
          service_type: 'api',
          service_name: 'test-api',
          version: '1.0.0',
          status: 'running',
          metadata: {},
          last_heartbeat: '2024-01-01T00:00:00Z',
          registered_at: '2024-01-01T00:00:00Z',
        },
      ];

      (apiClient.get as jest.Mock).mockResolvedValue(mockInstances);

      const result = await repository.getInstancesByStatus('running');

      expect(apiClient.get).toHaveBeenCalledWith('/instances/status/running');
      expect(result).toEqual(mockInstances);
    });

    it('should handle invalid response format', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue({});

      await expect(repository.getInstancesByStatus('running')).rejects.toThrow(
        'Invalid response format for service instances'
      );
    });
  });

  describe('getHealthSummary', () => {
    it('should fetch health summary', async () => {
      const mockHealthSummary = {
        total_services: 5,
        healthy_services: 4,
        unhealthy_services: 1,
        degraded_services: 0,
        service_types: {
          api: { healthy: 2, unhealthy: 0 },
          worker: { healthy: 2, unhealthy: 1 },
        },
        last_updated: '2024-01-01T00:00:00Z',
      };

      (apiClient.get as jest.Mock).mockResolvedValue(mockHealthSummary);

      const result = await repository.getHealthSummary();

      expect(apiClient.get).toHaveBeenCalledWith('/instances/health/summary');
      expect(result).toEqual(mockHealthSummary);
    });

    it('should handle invalid response format', async () => {
      (apiClient.get as jest.Mock).mockResolvedValue('invalid');

      await expect(repository.getHealthSummary()).rejects.toThrow(
        'Invalid response format for health summary'
      );
    });
  });
});
