# aegis-sdk-dev Issues and Gaps Found

This document tracks issues, limitations, and improvement opportunities discovered while implementing the echo-service-ddd example using aegis-sdk-dev bootstrap tools.

## Issues Found

### Issue #1: Python Standard Library Naming Conflict
**Problem**: Bootstrap template creates a `types` directory which conflicts with Python's standard library `types` module.
**Impact**: Causes import errors when trying to run the application.
**Workaround**: Renamed `types` directory to `type_definitions`.
**Suggested Fix**: Update template to use a non-conflicting name like `type_defs` or `contracts`.

### Issue #2: Empty Domain Services File
**Problem**: Bootstrap generates domain/services.py with only a TODO comment, providing no structure or examples.
**Impact**: Developer must figure out domain service patterns from scratch.
**Suggested Fix**: Include at least one example domain service with proper DDD patterns.

### Issue #3: Generic Repository Examples
**Problem**: Bootstrap creates generic `UserRepository` example instead of domain-specific repositories.
**Impact**: Not helpful for understanding how to create domain-appropriate repositories.
**Suggested Fix**: Generate repository interfaces based on the project name or include better examples.

### Issue #4: Empty Domain Events File
**Problem**: Bootstrap generates domain/events.py with only a TODO comment.
**Impact**: No guidance on implementing domain events following DDD principles.
**Suggested Fix**: Include base DomainEvent class and at least one example event.

### Issue #5: Missing Application Layer Structure
**Problem**: Application layer files are mostly empty or have generic examples.
**Impact**: No clear guidance on implementing use cases, command/query handlers.
**Suggested Fix**: Provide better scaffolding for application layer components.

### Issue #6: No Infrastructure Implementation Examples
**Problem**: Infrastructure layer lacks concrete implementation examples for adapters.
**Impact**: Developers must figure out ports/adapters pattern implementation alone.
**Suggested Fix**: Include at least one complete adapter implementation example.

## Positive Aspects

1. Good overall project structure following hexagonal architecture
2. Includes test structure with pytest configuration
3. Proper Python packaging with pyproject.toml
4. Includes Docker and Kubernetes manifests
5. Environment configuration with .env.example

## Recommendations

1. **Improve Template Content**: Instead of empty files with TODOs, provide minimal but functional examples that demonstrate DDD patterns.

2. **Add Documentation**: Include a ARCHITECTURE.md file explaining the DDD/hexagonal architecture decisions and patterns used.

3. **Better Naming**: Avoid Python standard library conflicts in generated directory/file names.

4. **Interactive Customization**: Allow specifying domain concepts during bootstrap (e.g., main entity names, use cases).

5. **Pattern Library**: Include a patterns directory with common DDD pattern implementations for reference.

6. **Validation Improvements**: The aegis-validate command could provide more specific guidance on what's missing or misconfigured.

### Issue #7: No Use Case Examples in Application Layer
**Problem**: The bootstrap template doesn't include any use case implementations in the application layer.
**Impact**: Developers must create use cases from scratch without guidance on proper structure.
**Suggested Fix**: Include at least one complete use case example showing orchestration of domain services.

### Issue #8: Placeholder User-focused DTOs/Commands
**Problem**: Bootstrap generates User-centric DTOs, commands, and queries even when the domain has nothing to do with users.
**Impact**: All placeholder code must be replaced, providing no value.
**Suggested Fix**: Generate generic or configurable domain-appropriate examples based on project name.

### Issue #9: Missing Repository Interface in Domain
**Problem**: While repository interfaces are created, they don't follow proper DDD aggregate repository patterns.
**Impact**: Developers may not understand the repository pattern correctly.
**Suggested Fix**: Include proper aggregate root repository interfaces with clear documentation.

### Issue #10: No Integration Between Layers
**Problem**: Bootstrap doesn't show how layers should connect - no factory or dependency injection setup.
**Impact**: Developers must figure out how to wire layers together.
**Suggested Fix**: Include a basic factory pattern or dependency injection container example.

### Issue #11: K8s Template Structure Incorrect
**Problem**: Bootstrap generates k8s directory with templates directly in it, but Helm expects them in a templates/ subdirectory.
**Impact**: Helm chart doesn't work without reorganizing files.
**Workaround**: Manually move template files to k8s/templates/ directory.
**Suggested Fix**: Generate proper Helm chart structure with templates/ subdirectory.

### Issue #12: Missing Helm Helpers Template
**Problem**: Bootstrap generates placeholder _helpers.tpl with just a TODO comment.
**Impact**: Common Helm template functions are missing, causing template errors.
**Workaround**: Manually implement all helper templates.
**Suggested Fix**: Include standard Helm helper templates for labels, names, etc.

### Issue #13: Incomplete values.yaml
**Problem**: Generated values.yaml lacks essential configuration for probes, resources, NATS, etc.
**Impact**: Chart not production-ready without significant additions.
**Suggested Fix**: Include comprehensive default values for all common Kubernetes settings.

### Issue #14: aegis-validate False Positives
**Problem**: aegis-validate reports missing k8s directory and Dockerfile even when they exist.
**Impact**: Confusing validation output that doesn't reflect actual project state.
**Suggested Fix**: Fix path detection logic in validation tool.

### Issue #15: No ServiceAccount in Helm Chart
**Problem**: Bootstrap doesn't generate ServiceAccount template which is often required.
**Impact**: Manual creation needed for proper RBAC in Kubernetes.
**Suggested Fix**: Include ServiceAccount template with configurable RBAC settings.

### Issue #16: Missing Environment-Specific Values
**Problem**: No examples of values-dev.yaml or values-prod.yaml for different environments.
**Impact**: Users must figure out environment configuration patterns themselves.
**Suggested Fix**: Include example environment-specific values files.

### Issue #17: No Integration Test Examples
**Problem**: Bootstrap generates test files but no integration test examples using testcontainers.
**Impact**: No guidance on testing with real infrastructure dependencies.
**Suggested Fix**: Include at least one integration test example with NATS testcontainer.

### Issue #18: aegis-test Command Missing
**Problem**: Documentation mentions aegis-test but command doesn't exist or isn't installed.
**Impact**: Can't use the advertised testing functionality.
**Suggested Fix**: Implement or properly expose the aegis-test command.

### Issue #19: No Main.py Entry Point
**Problem**: Bootstrap doesn't create a functional main.py to run the service.
**Impact**: Service can't be started without implementing entry point from scratch.
**Suggested Fix**: Generate working main.py that wires up all layers and starts service.

### Issue #20: Missing AegisSDK Integration
**Problem**: Bootstrap doesn't include examples of using aegis_sdk for service bus, health checks, etc.
**Impact**: Developers must figure out SDK integration patterns themselves.
**Suggested Fix**: Include examples showing proper AegisSDK usage in infrastructure layer.

## Workarounds Documentation

### K8s Deployment Workaround
1. Move all .yaml and .tpl files except Chart.yaml and values*.yaml to k8s/templates/
2. Implement _helpers.tpl with standard Helm helper functions
3. Add comprehensive configuration to values.yaml including probes, resources, and service configs
4. Create ServiceAccount template manually
5. Create environment-specific values files

### Testing Workaround
1. Install pytest and testcontainers manually: `pip install pytest pytest-asyncio testcontainers`
2. Run tests with: `python -m pytest tests/ -v`
3. For coverage: `python -m pytest tests/ --cov=. --cov-report=term-missing`

### AegisSDK Integration Workaround
1. Study existing services in apps/ directory for SDK usage patterns
2. Implement factory pattern manually for dependency injection
3. Create adapters for NATS, KV store, and monitor API integration

## Improvements to Bootstrap Templates

1. **Template Quality**: Replace TODO placeholders with minimal working examples
2. **Project Customization**: Add prompts for domain entity names, use cases, and service type
3. **Documentation**: Generate README with architecture explanation and setup instructions
4. **SDK Integration**: Include AegisSDK integration examples in infrastructure layer
5. **Testing Setup**: Include working test examples with proper fixtures and mocks
6. **Entry Points**: Generate functional main.py and Docker entrypoint
7. **K8s Structure**: Create proper Helm chart structure with all necessary templates
8. **Validation Accuracy**: Fix path detection and validation logic

## SDK Pattern Inconsistencies

1. **Import Patterns**: Bootstrap uses relative imports but SDK examples use absolute
2. **Async Patterns**: No guidance on async/await usage which is required by SDK
3. **Error Handling**: No examples of proper error handling patterns used by SDK
4. **Configuration**: Bootstrap uses different config patterns than SDK services
5. **Logging**: No logging setup despite SDK requiring structured logging

## Next Steps

- Create PR with fixes for critical issues (naming conflicts, structure problems)
- Enhance bootstrap templates with working examples
- Improve validation tool accuracy
- Add comprehensive documentation to generated projects

## Critical Issues from Latest Debugging Session (2025-08-11)

### Issue #21: NATSAdapter Method Mismatch
**Problem**: Generated adapters use incorrect NATSAdapter methods (e.g., `publish` instead of `publish_event`)
**Impact**: Runtime errors when handling RPC calls
**Root Cause**: Template doesn't understand actual AegisSDK API
**Suggested Fix**: Generate adapters that correctly use NATSAdapter's actual methods

### Issue #22: Missing Pre-validation in Build Process
**Problem**: Docker builds happen without validating Python code first
**Impact**: Broken images deployed to K8s, causing CrashLoopBackOff
**Suggested Fix**: Add mandatory test-local step before docker-build in Makefile template

### Issue #23: Helm Deployment Uses Wrong Image Tags
**Problem**: helm-upgrade doesn't specify image version, defaults to latest which may not exist
**Impact**: ImagePullBackOff errors in K8s
**Suggested Fix**: Makefile should always extract and use versioned tags for Helm deployments

### Issue #24: Health Check Configuration Mismatch
**Problem**: K8s templates configure HTTP health checks but service doesn't implement HTTP endpoints
**Impact**: Pods never become ready, constant restarts
**Suggested Fix**: Either disable health checks by default or generate HTTP health endpoint in main.py

### Issue #25: Proxy Configuration Not Inherited
**Problem**: Docker build doesn't automatically load proxy settings from root .env
**Impact**: Build failures in environments requiring proxy
**Suggested Fix**: Makefile should search parent directories for .env and load proxy settings

### Issue #26: Service Factory Pattern Missing
**Problem**: No factory pattern for dependency injection in generated code
**Impact**: Developers must create complex wiring logic from scratch
**Suggested Fix**: Generate ServiceFactory class with proper initialization patterns

### Issue #27: RPC Handler Registration Incorrect
**Problem**: Template uses JetStream for RPC handlers instead of direct NATS subscription
**Impact**: RPC calls fail with "NotFoundError"
**Suggested Fix**: Use correct pattern for RPC vs event subscriptions
