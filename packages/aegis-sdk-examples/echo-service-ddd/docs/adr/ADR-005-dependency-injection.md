# ADR-005: Dependency Injection with Factory Pattern

## Status
Accepted

## Context
We need a way to wire together components from different layers while maintaining loose coupling and testability. The solution must be simple, explicit, and not require a complex DI framework.

## Decision
We will use a Factory pattern for dependency injection:
- `ServiceFactory` class centralizes object creation
- Explicit dependency wiring in factory
- Factory creates fully configured use cases
- No auto-wiring or reflection magic
- Dependencies injected via constructor
- Singleton factory instance per service lifecycle

## Consequences

### Positive
- Explicit and easy to understand
- No framework dependencies
- Easy to test with mock factories
- Clear dependency graph
- Type-safe with proper hints

### Negative
- Manual wiring can be tedious
- Factory can become large
- No automatic lifecycle management
- Potential for factory to become god object

## Implementation
- Factory implementation in `infra/factory.py`
- Factory creates use cases with all dependencies
- Main entry point gets factory instance
- Tests can provide mock factories

## Example
```python
factory = ServiceFactory(config)
echo_use_case = factory.create_echo_use_case()
result = await echo_use_case.execute(request)
```
