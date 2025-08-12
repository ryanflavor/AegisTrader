# test-example

Project documentation

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Setup

### Using uv (recommended)

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Development

```bash
# Run the application
uv run python main.py

# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check --fix .

# Type checking
uv run mypy .
```

## Docker

```bash
# Build image
docker build -t test-example .

# Run container
docker run -p 8080:8080 test-example
```

## Kubernetes/Helm

```bash
# Deploy with Helm
helm install test-example ./k8s -f k8s/values.yaml

# Or apply directly
kubectl apply -f k8s/
```
