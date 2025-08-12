# **2.0 Tech Stack**

| Category | Technology | Version | Rationale & Purpose |
| :---- | :---- | :---- | :---- |
| **Backend Language** | Python | 3.13+ | Core SDK and management service development language. |
| **Backend Framework** | FastAPI | latest | High-performance for building the management API, with native Pydantic integration. |
| **Frontend Language** | TypeScript | latest | Provides strong type safety, crucial for large, maintainable frontend applications. |
| **Frontend Framework** | Next.js | latest | A production-grade React framework supporting SSR/SSG and API routes, ideal for fast web apps. |
| **UI Components** | Shadcn/ui | latest | A highly customizable and composable UI component set based on Tailwind CSS, offering great flexibility. |
| **CSS Utility** | Tailwind CSS | latest | A utility-first CSS framework that serves as the foundation for Shadcn/ui. |
| **Frontend State** | Zustand | latest | A lightweight and simple state management library, avoiding the complexity of traditional alternatives. |
| **Core Messaging** | NATS & JetStream | 2.9+ | The core system platform, providing RPC, events, commands, and persistence. |
| **Service Registry** | NATS KV Store | N/A | Implements a high-availability service registry without external database dependencies. |
| **Backend Testing** | Pytest | \>=7.0.0 | The standard testing framework for Python, with support for async testing. |
| **Containerization** | Docker | latest | Packages all applications into standardized container images for environmental consistency. |
| **Orchestration** | Kubernetes | latest | Automates deployment, scaling, and management of containerized applications for high availability. |
| **IaC Tool** | Helm Charts | latest | Defines and manages all application deployments on Kubernetes. |
| **CI/CD Pipeline** | GitHub Actions | latest | Automates code integration, testing, building, and deployment pipelines. |
