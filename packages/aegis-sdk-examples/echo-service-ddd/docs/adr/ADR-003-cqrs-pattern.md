# ADR-003: Command Query Responsibility Segregation (CQRS)

## Status
Accepted

## Context
The service needs to handle both command operations (that change state) and query operations (that retrieve data). We want to optimize each type of operation independently and maintain clear separation of concerns.

## Decision
We will implement a lightweight CQRS pattern:
- Separate Command and Query objects
- Dedicated handlers for each command and query
- Commands return minimal acknowledgment
- Queries return rich DTOs
- Same data store for both (no event sourcing)

## Consequences

### Positive
- Clear separation between reads and writes
- Can optimize queries independently
- Explicit command/query intent
- Easier to add cross-cutting concerns per operation type
- Natural fit with hexagonal architecture

### Negative
- More classes (commands, queries, handlers)
- Potential code duplication
- Overkill for simple CRUD operations

## Implementation
- Commands in `application/commands.py`
- Queries in `application/queries.py`
- Handlers in `application/handlers.py`
- Use cases orchestrate command/query execution
