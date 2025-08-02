# Contributing to AegisTrader

Thank you for your interest in contributing to AegisTrader! This guide will help you get started.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/realAnthony/AegisTrader.git
   cd AegisTrader
   ```

2. **Install dependencies:**
   ```bash
   # Install uv if you haven't already
   pip install uv

   # Sync project dependencies
   uv sync
   ```

3. **Set up pre-commit hooks:**
   ```bash
   ./scripts/setup-pre-commit.sh
   ```

## Code Quality Standards

All code must pass the following checks before being merged:

### Formatting
- **Black**: Python code formatter (100 char line length)
- **isort**: Import sorting
- **Ruff**: Fast Python linter

### Type Checking
- **MyPy**: Static type checking for Python

### Security
- **Bandit**: Security linter for Python
- **detect-secrets**: Prevents secrets from being committed

### Other Checks
- YAML validation
- JSON validation
- Trailing whitespace removal
- File ending fixes
- Large file detection

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions or modifications
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Other changes

### Examples
```
feat(sdk): add retry logic to NATS adapter

fix(monitor-api): resolve memory leak in WebSocket handler

docs: update deployment instructions for Kubernetes
```

## Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_specific.py
```

### Writing Tests
- Place tests in the `tests/` directory
- Follow the existing test structure
- Aim for >80% code coverage
- Include both unit and integration tests

## Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Write clean, documented code
   - Add tests for new functionality
   - Update documentation as needed

3. **Run pre-commit checks:**
   ```bash
   pre-commit run --all-files
   ```

4. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push and create PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **PR Requirements:**
   - Clear description of changes
   - All CI/CD checks passing
   - Code review approval
   - No merge conflicts

## Code Style Guidelines

### Python
- Follow PEP 8 with 100-character line limit
- Use type hints for function parameters and returns
- Document classes and functions with docstrings
- Prefer descriptive variable names

### Example:
```python
from typing import Optional

async def process_trade_signal(
    symbol: str,
    signal_type: str,
    confidence: float
) -> Optional[dict[str, Any]]:
    """Process incoming trade signal and return action if applicable.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        signal_type: Type of signal ("buy", "sell", "hold")
        confidence: Confidence level (0.0 to 1.0)

    Returns:
        Action dict if trade should be executed, None otherwise
    """
    if confidence < 0.7:
        return None

    return {
        "action": signal_type,
        "symbol": symbol,
        "confidence": confidence,
        "timestamp": datetime.utcnow()
    }
```

## Architecture Guidelines

### Hexagonal Architecture
- Keep domain logic separate from infrastructure
- Use ports and adapters pattern
- Dependency injection for flexibility

### Directory Structure
```
packages/aegis-sdk/
├── aegis_sdk/
│   ├── domain/          # Business logic
│   ├── application/     # Use cases
│   ├── infrastructure/  # External adapters
│   └── ports/          # Interfaces
```

## Getting Help

- Check existing issues and discussions
- Join our community chat (if available)
- Create an issue for bugs or feature requests

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
