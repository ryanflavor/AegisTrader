# **4.0 API Interface Contracts**

## **4.1 Management Service (FastAPI) \- RESTful API Contract**

YAML

openapi: 3.0.0  
info:  
  title: "AegisSDK Management API"  
  version: "1.0.0"  
paths:  
  /services:  
    get:  
      summary: "Get list of all service definitions"  
    post:  
      summary: "Create a new service definition"  
  /services/{serviceName}:  
    put:  
      summary: "Update an existing service definition"  
    delete:  
      summary: "Delete a service definition"  
  /metrics/live:  
    get:  
      summary: "Get real-time metrics for all healthy service instances"  
components:  
  schemas:  
    ServiceDefinition: { ... }  
    ServiceInstance: { ... }

## **4.2 NATS Internal Messaging Contracts**

* **Order Submission (RPC)**: Uses the subject rpc.trading-service.{accountId}.send\_order with a payload containing fields like symbol, exchange, direction, type, volume, and price.  
* **Trade Report (Event)**: Uses the subject events.trading.{accountId}.trade with a payload containing fields like symbol, order\_id, trade\_id, price, and volume.
