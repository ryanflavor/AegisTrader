# **Technical Assumptions**

## **Repository Structure**
The project will be organized as a **Monorepo** to facilitate the sharing of code and types between the backend and frontend.

## **Service Architecture**
The system will consist of a **FastAPI** backend for the management API, a **Next.js** frontend for the UI, and the core business services running on the enhanced **AegisSDK**.

## **Testing requirements**
All new functionality must be accompanied by unit and integration tests. A performance baselining suite must be created as part of the initial epic.

## **Additional Technical Assumptions and Requests**
The service registry will be implemented using the **NATS KV Store** to avoid introducing external database dependencies.

---
