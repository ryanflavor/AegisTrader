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
  status: 'ACTIVE' | 'UNHEALTHY' | 'STANDBY';  
  stickyActiveGroup?: string;  
  lastHeartbeat: string;  
  metadata?: Record\<string, any\>;  
}
