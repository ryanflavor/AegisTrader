# **12.0 Testing Strategy**

* **Methodology**: **Test-Driven Development (TDD)** (Red-Green-Refactor) is the mandatory development workflow.  
* **Coverage**: A minimum of **80%** overall test coverage is required, with **100%** coverage for all critical paths and business logic.  
* **Integration Testing**: **testcontainers** must be used to test against real dependencies like NATS, forbidding the mocking of core external services.  
* **Naming**: Test functions must follow the test\_{functionality}\_{expected\_behavior} convention.
