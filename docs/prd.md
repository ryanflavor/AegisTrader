# **AegisSDK Enhancement Product Requirements Document (PRD)**

## **Goals and Background Context**

### **Goals**
The primary goal of this project is to enhance the existing **AegisSDK** to support a distributed trading system. This involves delivering a framework with a persistent **service registry**, a **"sticky single-active" RPC pattern** for high availability, and a web-based **monitoring and management UI**.

### **Background Context**
The `AegisSDK` is a lightweight, high-performance IPC framework. To be applied to production-grade trading systems—which have stringent requirements for reliability and observability—it must be augmented with centralized service management, real-time monitoring, and a high-availability communication pattern suitable for specific trading scenarios.

### **Change Log**
| Date | Version | Description | Author |
| :--- | :--- | :--- | :--- |
| 2025-07-31 | 1.0 | Final, standardized version | John (PM) |

---
## **Requirements**

### **Functional**
* **FR1**: The system must provide a web-based monitoring and management interface.
* **FR2**: The interface must display real-time performance metrics for each service instance, including RPC latencies, success/error rates, and queue depths.
* **FR3**: The system must provide a highly available service registry using the **NATS KV Store** for persistence.
* **FR4**: A management service, built with **FastAPI**, must expose a secure HTTP API for full CRUD (Create, Read,
    Update, Delete) management of service definitions.
* **FR5**: The SDK must support externalized configuration for parameters like connection pool size and RPC
    timeouts.
* **FR6**: The management API must provide an endpoint to view the current configuration of any service instance.
* **FR7**: The SDK must implement a "Sticky Single-Active" RPC pattern with synchronous responses and automatic
    failover.

### **Non Functional**
* **NFR1**: Performance baselines must be established for the existing SDK before new development begins.
* **NFR2**: New features must not degrade the baseline p99 RPC latency by more than 10%.
* **NFR3**: The failover process for the "Sticky Single-Active" pattern must complete within 2 seconds.
* **NFR4**: All enhancements must be backward compatible.
* **NFR5**: The management interface and its API must be secured against unauthorized access.
* **NFR6**: No single point of failure shall exist in the system's core components.
* **NFR7**: All critical persistent data must be replicated across multiple nodes.
* **NFR8**: The `AegisSDK` client must handle NATS node failures with transparent, automatic failover.

---
## **User Interface Design Goals**

### **Overall UX Vision**
To create a clean, professional, and information-dense monitoring and management interface that prioritizes data clarity and operational efficiency for technical and operations personnel.

### **Core Screens and Views**
* **Dashboard**: A global overview displaying all registered service instances and their health status.
* **Service Detail View**: A page for deep-dive analysis of a single instance's real-time and historical performance metrics.
* **Configuration View**: A section to display the current configuration of a selected service.
* **Service Management**: A full CRUD interface for managing service definitions within the registry.

### **Accessibility**
The application should adhere to WCAG 2.1 Level AA standards where feasible.

### **Branding**
The interface will use a clean, professional theme suitable for a technical tool. No complex branding is required for the initial version.

### **Target Device and Platforms**
The primary target is a responsive web interface for desktop browsers.

---
## **Technical Assumptions**

### **Repository Structure**
The project will be organized as a **Monorepo** to facilitate the sharing of code and types between the backend and frontend.

### **Service Architecture**
The system will consist of a **FastAPI** backend for the management API, a **Next.js** frontend for the UI, and the core business services running on the enhanced **AegisSDK**.

### **Testing requirements**
All new functionality must be accompanied by unit and integration tests. A performance baselining suite must be created as part of the initial epic.

### **Additional Technical Assumptions and Requests**
The service registry will be implemented using the **NATS KV Store** to avoid introducing external database dependencies.

---
## **Epics**

The project is broken down into the following epics and stories:

* **Epic 0**: Infrastructure & Deployment Pipeline
* **Epic 1**: Existing Feature Validation & Performance Benchmarks
* **Epic 2**: NATS KV Store-Based Service Registry
* **Epic 3**: Sticky Single-Active RPC Pattern Implementation
* **Epic 4**: Monitoring & Management System

### **Epic 0: Infrastructure & Deployment Pipeline**
**Goal**: To build an automated, production-grade, Kubernetes-based deployment environment.

* **Story 0.1: Containerize Applications**
    * **As an** operations team, **I want** to package the `ManagementService (FastAPI)` and `MonitorUI (Next.js)` applications into Docker images **so that** they can be deployed consistently across all environments.
    * **Acceptance Criteria (AC):**
        1.  The project contains a valid `Dockerfile` for the FastAPI application.
        2.  The project contains a valid `Dockerfile` for the Next.js application.
        3.  Both images can be successfully built and run locally.

* **Story 0.2: Deploy Kubernetes Base Environment**
    * **As an** operations team, **I want** to use Infrastructure as Code (IaC) to define and deploy a base Kubernetes environment **so that** our applications have a standardized runtime platform.
    * **Acceptance Criteria (AC):**
        1.  The project contains Helm charts for deploying the NATS cluster.
        2.  The project contains Helm charts for deploying the FastAPI and Next.js applications.
        3.  A single command can deploy the entire stack to a Kubernetes cluster.

* **Story 0.3: Establish CI/CD Automation Pipeline**
    * **As a** development team, **I want** an automated CI/CD pipeline **so that** every code change is automatically tested, built, and deployed to the Kubernetes environment.
    * **Acceptance Criteria (AC):**
        1.  A CI/CD configuration file (e.g., for GitHub Actions) is present in the repository.
        2.  On every push to the main branch, the pipeline automatically runs all tests.
        3.  If tests pass, the pipeline builds and pushes new Docker images to a registry.
        4.  The pipeline automatically deploys the new images to a staging environment in Kubernetes.

### **Epic 1: Existing Feature Validation & Performance Benchmarks**
**Goal**: To ensure a stable foundation by verifying the current SDK's correctness and establishing performance baselines.

* **Story 1.1: Core Feature Correctness Validation**
    * **As a** development team, **I want** to verify that all existing SDK features are working correctly and have adequate test coverage **so that** we have a stable foundation for new enhancements.
    * **Acceptance Criteria (AC):**
        1.  Executing the full `pytest` suite passes without errors.
        2.  The code coverage report shows at least 90% coverage for the core SDK logic.
        3.  A QA review confirms that RPC, Event, and Command patterns function as described in the `README.md`.

* **Story 1.2: Key Communication Patterns Performance Benchmarking**
    * **As a** system architect, **I want** to establish and document the baseline performance for the core RPC and Event communication patterns **so that** we can objectively measure the performance impact of new features.
    * **Acceptance Criteria (AC):**
        1.  A repeatable performance test script is created.
        2.  The p99 latency and max throughput (requests/sec) for the RPC pattern are measured and recorded.
        3.  The publish latency and max throughput (events/sec) for the JetStream Event pattern are measured and recorded.

### **Epic 2: NATS KV Store-Based Service Registry**
**Goal**: To implement a highly available, persistent service registration and discovery center.

* **Story 2.1: Implement Service Registry HTTP Management API**
    * **As a** system administrator, **I want** a secure FastAPI endpoint to CRUD service definitions **so that** I can manage the lifecycle of services allowed in the system.
    * **Acceptance Criteria (AC):**
        1.  The `ManagementService` provides `POST`, `GET`, `PUT`, and `DELETE` endpoints for `/api/services`.
        2.  Each endpoint correctly manipulates service definition entries in the NATS KV Store.
        3.  All API endpoints are protected against unauthorized access.

* **Story 2.2: Integrate SDK Service Registration**
    * **As an** `AegisSDK` service instance, **I want** to register with the new Registry Service upon startup and send heartbeats **so that** my existence and health status are persistently tracked.
    * **Acceptance Criteria (AC):**
        1.  On startup, a service instance writes its `ServiceInstance` data to a key in the NATS KV Store.
        2.  The key is created with a specific TTL (Time-To-Live).
        3.  The service periodically updates the key to refresh the TTL, acting as a heartbeat.

* **Story 2.3: Implement Client-Side Service Discovery**
    * **As an** `AegisSDK` client, **I want** to query the Registry Service to discover available instances of a target service **so that** I always have an up-to-date list of healthy instances.
    * **Acceptance Criteria (AC):**
        1.  Before an RPC call, the client queries the NATS KV Store for all instance keys of the target service.
        2.  The client uses the returned list to select an instance for the call.
        3.  The client implements a caching strategy to avoid querying on every single call.

### **Epic 3: Sticky Single-Active RPC Pattern Implementation**
**Goal**: To implement a reliable, synchronous "sticky single-active" RPC pattern for critical business operations.

* **Story 3.1: Implement Sticky-Active Instance Election & Heartbeat**
    * **As an** `AegisSDK` service cluster, **I want** to elect a single "sticky active" instance for a service group and maintain its status via heartbeats **so that** there is always one designated instance for critical requests.
    * **Acceptance Criteria (AC):**
        1.  SingleActiveService implements the sticky single-active pattern through client-side retry.
        2.  On startup, instances of this class use an atomic "create-or-get" operation on a designated NATS KV Store key to elect a leader.
        3.  Only the elected leader instance sets its status to `ACTIVE` in its `ServiceInstance` record in the KV Store.
        4.  Standby instances periodically monitor the leader's heartbeat key.

* **Story 3.2: Implement Client-Side Discovery & Routing**
    * **As an** `AegisSDK` client, **I want** to discover and send an RPC request directly to the current "sticky active" instance **so that** my request is handled by the correct instance and I get a synchronous response.
    * **Acceptance Criteria (AC):**
        1.  When making a "sticky" call, the client queries the KV Store for the instance with `status: 'ACTIVE'`.
        2.  The client sends the RPC request to that specific instance.
        3.  If the call fails or the instance reports it's not active, the client clears its cache and retries the discovery.

* **Story 3.3: Implement Automatic Failover**
    * **As a** standby service instance, **I want** to detect when the active instance has failed and participate in a new election **so that** the service can quickly recover.
    * **Acceptance Criteria (AC):**
        1.  If a standby instance detects the leader's heartbeat key has expired (due to TTL), it triggers a new election.
        2.  A new leader is successfully elected and updates its status in the KV Store.
        3.  The entire failover process, from detection to the new leader being ready, completes in under 2 seconds.

### **Epic 4: Monitoring & Management System**
**Goal**: To build a comprehensive web interface for monitoring service status and managing configurations.

* **Story 4.1: Implement Monitoring Data API Endpoint**
    * **As an** operator, **I want** a secure API endpoint that provides real-time metrics for all service instances **so that** a web interface can display this data.
    * **Acceptance Criteria (AC):**
        1.  The `ManagementService` provides a secure `GET /api/metrics` endpoint.
        2.  The endpoint queries the NATS KV Store for all active `ServiceInstance` records.
        3.  The endpoint returns a JSON array of these records.

* **Story 4.2: Develop Monitoring Dashboard & Service Management UI**
    * **As a** system administrator, **I want** a dashboard for a high-level overview and a CRUD interface to manage service definitions **so that** I can monitor and manage the system from a single UI.
    * **Acceptance Criteria (AC):**
        1.  The Next.js UI fetches data from `/api/metrics` and displays a list or grid of service instances.
        2.  The UI provides forms and buttons to call the CRUD API endpoints for managing service definitions.
        3.  Unhealthy services are visually highlighted on the dashboard.

* **Story 4.3: Develop Service Detail & Configuration View UI**
    * **As an** operator, **I want** to view detailed metrics and the current configuration of a service **so that** I can perform deep-dive troubleshooting.
    * **Acceptance Criteria (AC):**
        1.  Clicking an instance on the dashboard navigates to a detailed view page for that instance.
        2.  The detail view displays historical metrics for the instance in a chart.
        3.  The detail view includes a section that calls a configuration endpoint to display the instance's current settings.
