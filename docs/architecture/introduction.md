# **Introduction**

This document outlines the architectural approach for enhancing the AegisTrader ecosystem with a new **Market Service**。 Its primary goal is to serve as the guiding architectural blueprint for AI-driven development of this new service, ensuring seamless integration with the existing AegisSDK platform。

Relationship to Existing Architecture:
This document defines how the new Market Service components will be built upon and integrate with the existing AegisSDK framework。 It translates the provided DDD design into a formal architectural plan.

## **Existing Project Analysis**

The new Market Service will be built on the existing AegisSDK platform.

**Current Project State:**

* **Primary Purpose**: The foundation is the AegisSDK, a lightweight, high-performance Inter-Process Communication (IPC) SDK for building microservices using NATS, following Hexagonal Architecture and DDD principles。 It is complemented by aegis-sdk-dev, a toolkit for rapid project scaffolding, code generation, and deployment。
* **Current Tech Stack**: The ecosystem is built on Python 3.13+, NATS (with JetStream and KV Store), Docker, and Kubernetes (using Helm)。
* **Architecture Style**: The enforced architecture is Hexagonal (Ports and Adapters) and Domain-Driven Design。
* **Deployment Method**: The standard deployment method is via containerized services orchestrated by Kubernetes。

**Available Documentation:**

* Comprehensive DDD design documents for the new Market Service (Domain Exploration, Strategic Design, Tactical Design, Architecture Patterns, and Overview).
* Detailed documentation for the AegisSDK runtime and the AegisSDK-dev toolkit.

**Identified Constraints:**

* The Market Service must be implemented using the AegisSDK framework and its components, such as Service and SingleActiveService。
* All inter-service communication must use NATS, following the patterns established by the SDK (RPC, Events, Commands)。
* The project structure and DevOps automation should leverage the aegis-sdk-dev toolkit。

## **Change Log**

| Change | Date | Version | Description | Author |
| :---- | :---- | :---- | :---- | :---- |
| Initial Draft | 2025-08-11 | 1.0 | Initial architecture based on DDD design | Winston (Architect) |
| **Revision** | **2025-08-11** | **1.1** | **Updated to reflect a single-service architecture per user feedback.** | **Winston (Architect)** |
