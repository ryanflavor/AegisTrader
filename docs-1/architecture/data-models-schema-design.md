# **3.0 Data Models & Schema Design**

## **3.1 Core Data Models**

* **ServiceDefinition**: Represents the static definition of a service type, managed by administrators and stored in the NATS KV Store.
* **ServiceInstance**: Contains the dynamic information of a running service instance, created on startup and periodically updated via heartbeat.

## **3.2 TypeScript Shared Interfaces**

TypeScript

// Located in packages/shared/src/types.ts
export interface ServiceDefinition {
  serviceName: string;
  owner: string;
  description: string;
  version: string;
  createdAt: string;
  updatedAt: string;
}
export interface ServiceInstance {
  serviceName: string;
  instanceId: string;
  version: string;
  status: 'ACTIVE' | 'UNHEALTHY' | 'STANDBY';  // Maps to ServiceStatus enum
  stickyActiveGroup?: string;
  stickyActiveStatus?: 'ACTIVE' | 'STANDBY' | 'ELECTING';  // Maps to StickyActiveStatus enum
  lastHeartbeat: string;
  metadata?: Record\<string, any\>;
}

// RPC Error codes for standardized error handling
export enum RPCErrorCode {
  NOT_ACTIVE = 'NOT_ACTIVE',  // Service instance is not the active leader
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',  // Service cannot be reached
  TIMEOUT = 'TIMEOUT',  // Request timed out
  INVALID_REQUEST = 'INVALID_REQUEST',  // Malformed or invalid request
  INTERNAL_ERROR = 'INTERNAL_ERROR',  // Internal service error
  ELECTING = 'ELECTING'  // Service is in election process
}
