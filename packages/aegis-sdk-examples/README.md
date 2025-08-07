# AegisSDK Examples

World-class example applications demonstrating Domain-Driven Design (DDD), hexagonal architecture, and Test-Driven Development (TDD) with AegisSDK.

## 🎯 Purpose

These examples are designed to:
- Teach best practices in microservice architecture
- Demonstrate proper use of AegisSDK features
- Provide production-ready templates
- Show real-world patterns and solutions

## 📚 Structure

```
aegis-sdk-examples/
├── basic/              # Foundational concepts
├── intermediate/       # Real-world patterns
├── advanced/          # Complex architectures
└── tutorials/         # Step-by-step guides
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install AegisSDK and developer tools
pip install aegis-sdk aegis-sdk-dev

# Start NATS (using Docker)
docker run -d --name nats -p 4222:4222 nats:latest
```

### Run Your First Example

```bash
cd basic/hello-world
python main.py
```

## 📖 Learning Path

### 1. Basic Examples (Start Here)

#### [hello-world](./basic/hello-world/)
- **Concepts**: Hexagonal architecture, ports & adapters, Pydantic v2
- **Skills**: Basic service structure, dependency injection, type safety
- **Time**: 30 minutes

#### [echo-service](./basic/echo-service/)
- **Concepts**: Bidirectional communication, message handling
- **Skills**: Request-response patterns, error handling
- **Time**: 45 minutes

#### [simple-rpc](./basic/simple-rpc/)
- **Concepts**: RPC patterns, service discovery
- **Skills**: Client-server communication, timeouts
- **Time**: 45 minutes

### 2. Intermediate Examples

#### [trading-service](./intermediate/trading-service/)
- **Concepts**: Domain modeling, aggregates, repositories
- **Skills**: DDD implementation, business logic encapsulation
- **Time**: 2 hours

#### [event-driven](./intermediate/event-driven/)
- **Concepts**: Event sourcing, event-driven architecture
- **Skills**: Async messaging, eventual consistency
- **Time**: 2 hours

#### [single-active](./intermediate/single-active/)
- **Concepts**: Leader election, failover handling
- **Skills**: High availability, state management
- **Time**: 3 hours

### 3. Advanced Examples

#### [saga-pattern](./advanced/saga-pattern/)
- **Concepts**: Distributed transactions, compensation logic
- **Skills**: Complex workflows, failure recovery
- **Time**: 4 hours

#### [cqrs-example](./advanced/cqrs-example/)
- **Concepts**: Command Query Responsibility Segregation
- **Skills**: Read/write separation, projection handling
- **Time**: 4 hours

#### [full-trading-system](./advanced/full-trading-system/)
- **Concepts**: Complete microservice ecosystem
- **Skills**: Service orchestration, monitoring, deployment
- **Time**: 1 day

## 🏗️ Architecture Principles

All examples follow these principles:

### Hexagonal Architecture (Ports & Adapters)
```
domain/           # Business logic (pure, no dependencies)
├── models.py    # Entities, value objects, aggregates
├── services.py  # Domain services
└── events.py    # Domain events

application/      # Use cases and orchestration
├── use_cases.py # Application services
└── dtos.py      # Data transfer objects

infrastructure/   # External world adapters
├── adapters.py  # Implementations of ports
└── config.py    # Configuration

ports/           # Interfaces (contracts)
├── inbound.py   # APIs, message handlers
└── outbound.py  # Repositories, external services
```

### Test-Driven Development (TDD)
1. **Red**: Write a failing test
2. **Green**: Write minimal code to pass
3. **Refactor**: Improve code while keeping tests green

### Pydantic v2 Type Safety
- Strict validation at boundaries
- Immutable value objects
- Comprehensive field validators
- Model configuration for different contexts

## 🧪 Testing Strategy

Each example includes:

### Unit Tests
```bash
pytest tests/unit/ -v
```
- Test business logic in isolation
- Mock external dependencies
- Fast feedback loop

### Integration Tests
```bash
pytest tests/integration/ -v
```
- Test with real infrastructure
- Verify adapter implementations
- End-to-end scenarios

### Coverage Reports
```bash
pytest tests/ --cov=. --cov-report=html
```

## 🐳 Deployment

### Docker
Each example includes a Dockerfile:
```bash
docker build -t example-service .
docker run -e NATS_URL=nats://host.docker.internal:4222 example-service
```

### Kubernetes
Deploy to Kubernetes cluster:
```bash
kubectl apply -f k8s/
```

## 📊 Monitoring & Observability

Examples demonstrate:
- Structured logging with correlation IDs
- Metrics collection (Prometheus format)
- Health checks and readiness probes
- Distributed tracing setup

## 🔧 Development Tools

Use the aegis-sdk-dev tools:

```bash
# Validate configuration
aegis-validate --service-name my-service

# Bootstrap new service from template
aegis-bootstrap --template trading-service

# Run interactive tests
aegis-test --interactive
```

## 📝 Best Practices Demonstrated

1. **Domain Modeling**
   - Rich domain models over anemic models
   - Value objects for immutability
   - Aggregates for consistency boundaries

2. **Error Handling**
   - Domain exceptions for business rules
   - Graceful degradation
   - Circuit breakers for external calls

3. **Configuration Management**
   - Environment-based configuration
   - Validation with Pydantic
   - Secrets management patterns

4. **Performance**
   - Async/await throughout
   - Connection pooling
   - Caching strategies

5. **Security**
   - Input validation
   - Authentication patterns
   - Authorization checks

## 🤝 Contributing

We welcome contributions! To add a new example:

1. Follow the established structure
2. Include comprehensive tests
3. Document learning objectives
4. Provide both Docker and K8s configs
5. Submit a pull request

## 📚 Additional Resources

- [AegisSDK Documentation](../aegis-sdk/README.md)
- [Developer Tools Guide](../aegis-sdk-dev/README.md)
- [Architecture Decision Records](./docs/adr/)
- [Performance Benchmarks](./docs/benchmarks/)

## 🆘 Getting Help

- Check example READMEs for specific guidance
- Use `aegis-validate` for configuration issues
- Open GitHub issues with the `examples` tag
- Join our Discord community

## 📄 License

All examples are provided under the same license as AegisSDK.

---

**Remember**: These examples are teaching tools. While they demonstrate production patterns, always review and adapt them to your specific requirements before deploying to production.