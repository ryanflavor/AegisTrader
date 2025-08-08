"""Simple project generator using data-driven templates."""

import os

from aegis_sdk_dev.domain.models import BootstrapConfig
from aegis_sdk_dev.domain.project_templates import ProjectTemplates


class SimpleProjectGenerator:
    """Generate projects from simple template definitions."""

    def __init__(self, template_generator=None):
        """Initialize with optional template generator for enterprise DDD templates."""
        self._template_generator = template_generator

    def generate_project(self, config: BootstrapConfig) -> dict[str, str]:
        """Generate project files from template."""
        files = {}
        base_dir = f"{config.output_dir}/{config.project_name}"

        # Get template definition
        template = ProjectTemplates.get_template(config.template.value)

        # Create all files with simple descriptive content
        for file_path, description in template.get("files", {}).items():
            full_path = f"{base_dir}/{file_path}"
            content = self._generate_file_content(file_path, description, config)
            files[full_path] = content

        return files

    def _generate_file_content(
        self, file_path: str, description: str, config: BootstrapConfig
    ) -> str:
        """Generate file content based on file type and description."""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1]

        # Check if we have a template generator for enterprise DDD content
        if self._template_generator and config.template.value == "enterprise_ddd":
            # Map file names to generator methods
            method_mapping = {
                "entities.py": "generate_domain_entities",
                "value_objects.py": "generate_domain_value_objects",
                "repositories.py": "generate_domain_repositories",
                "commands.py": "generate_commands",
                "queries.py": "generate_queries",
                "handlers.py": "generate_handlers",
                "persistence.py": "generate_persistence",
                "messaging.py": "generate_messaging",
                "translators.py": "generate_translators",
                "anti_corruption.py": "generate_anti_corruption",
                "utils.py": "generate_utils",
                "validators.py": "generate_validators",
                "dto.py": "generate_dto",
                "interfaces.py": "generate_interfaces",
            }

            if file_name in method_mapping:
                method_name = method_mapping[file_name]
                if hasattr(self._template_generator, method_name):
                    method = getattr(self._template_generator, method_name)
                    return method(config)

        # Python files
        if file_ext == ".py":
            if file_name == "__init__.py":
                return f'"""{description} for {config.project_name}."""\n'
            elif file_name == "main.py":
                return f'''"""{description} for {config.project_name}."""

if __name__ == "__main__":
    print("Starting {config.project_name}...")
'''
            elif "test_" in file_name:
                return f'''"""{description} for {config.project_name}."""

import pytest


def test_placeholder():
    """Placeholder test."""
    assert True
'''
            else:
                return f'''"""{description} for {config.project_name}."""

# TODO: Implement {description.lower()}
'''

        # Requirements file (for compatibility, but uv uses pyproject.toml)
        elif file_name == "requirements.txt":
            return """# Dependencies are managed in pyproject.toml
# This file is kept for compatibility
# Use: uv pip install -e .
"""

        # Docker files
        elif file_name == "Dockerfile":
            return f"""# {description}
FROM python:3.13-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY . .

# Install dependencies with uv
RUN uv pip install --system -e .

CMD ["python", "main.py"]
"""

        elif file_name == ".dockerignore":
            return """*.pyc
__pycache__
.pytest_cache
.coverage
*.egg-info
.git
.venv
"""

        elif file_name == "docker-compose.yml":
            return f"""# {description}
version: '3.8'
services:
  {config.project_name}:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ENV=development
"""

        # Kubernetes YAML files (Helm-compatible)
        elif file_ext == ".yaml" and "k8s" in file_path:
            if "deployment" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
spec:
  replicas: {{{{ .Values.replicaCount | default 1 }}}}
  selector:
    matchLabels:
      {{{{- include "{config.project_name}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      labels:
        {{{{- include "{config.project_name}.selectorLabels" . | nindent 8 }}}}
    spec:
      containers:
      - name: {{{{ .Chart.Name }}}}
        image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
        imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
        ports:
        - name: http
          containerPort: {{{{ .Values.service.targetPort | default 8080 }}}}
          protocol: TCP
        resources:
          {{{{- toYaml .Values.resources | nindent 10 }}}}
"""
            elif "service" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
  - port: {{{{ .Values.service.port }}}}
    targetPort: http
    protocol: TCP
    name: http
  selector:
    {{{{- include "{config.project_name}.selectorLabels" . | nindent 4 }}}}
"""
            elif "configmap" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}-config
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
data:
  {{{{- range $key, $value := .Values.config }}}}
  {{{{ $key }}}}: {{{{ $value | quote }}}}
  {{{{- end }}}}
"""
            elif "ingress" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
{{{{- if .Values.ingress.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.ingress.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
spec:
  {{{{- if .Values.ingress.tls }}}}
  tls:
  {{{{- range .Values.ingress.tls }}}}
  - hosts:
    {{{{- range .hosts }}}}
    - {{{{ . | quote }}}}
    {{{{- end }}}}
    secretName: {{{{ .secretName }}}}
  {{{{- end }}}}
  {{{{- end }}}}
  rules:
  {{{{- range .Values.ingress.hosts }}}}
  - host: {{{{ .host | quote }}}}
    http:
      paths:
      {{{{- range .paths }}}}
      - path: {{{{ .path }}}}
        pathType: {{{{ .pathType }}}}
        backend:
          service:
            name: {{{{ include "{config.project_name}.fullname" $ }}}}
            port:
              number: {{{{ $.Values.service.port }}}}
      {{{{- end }}}}
  {{{{- end }}}}
{{{{- end }}}}
"""
            elif "values" in file_name:
                return f"""# {description}
# Default values for {config.project_name}
# This is a YAML-formatted file.
# Declare variables to be passed into your templates.

replicaCount: 1

image:
  repository: {config.project_name}
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: false
  annotations: {{}}
    # kubernetes.io/ingress.class: nginx
    # kubernetes.io/tls-acme: "true"
  hosts:
    - host: {config.project_name}.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []
  #  - secretName: {config.project_name}-tls
  #    hosts:
  #      - {config.project_name}.local

resources: {{}}
  # limits:
  #   cpu: 100m
  #   memory: 128Mi
  # requests:
  #   cpu: 100m
  #   memory: 128Mi

config:
  app.name: {config.project_name}
  app.env: production
"""
            elif "Chart" in file_name:
                return f"""# {description}
apiVersion: v2
name: {config.project_name}
description: A Helm chart for {config.project_name}
type: application
version: 0.1.0
appVersion: "1.0.0"
"""
            elif "_helpers" in file_name:
                return f"""# {description}
{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{config.project_name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
*/}}}}
{{{{- define "{config.project_name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Create chart name and version as used by the chart label.
*/}}}}
{{{{- define "{config.project_name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{config.project_name}.labels" -}}}}
helm.sh/chart: {{{{ include "{config.project_name}.chart" . }}}}
{{{{ include "{config.project_name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{config.project_name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{config.project_name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}
"""
            else:
                return f"# {description}\n# TODO: Configure this resource\n"

        # Configuration files
        elif file_name == "pyproject.toml":
            return f"""# {description}
[project]
name = "{config.project_name}"
version = "0.1.0"
description = "Generated with AegisTrader SDK"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "click>=8.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{config.project_name}"]

[tool.ruff]
line-length = 100
target-version = "py313"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --cov={config.project_name} --cov-report=term-missing"

[tool.uv]
dev-dependencies = [
    "ipython>=8.0.0",
    "ipdb>=0.13.0",
]
"""

        elif file_name == ".python-version":
            return "3.13\n"

        elif file_name == ".gitignore":
            return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
ENV/
env.bak/
venv.bak/

# uv
.venv/
uv.lock

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/
.nox/
coverage.xml
*.cover
.hypothesis/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Project
*.log
*.db
*.sqlite
.env
!.env.example

# Build
dist/
build/
*.egg-info/
.eggs/
*.egg

# Docker
*.pid
"""

        elif file_name == ".env.example":
            return f"""# {description}
APP_NAME={config.project_name}
APP_ENV=development
APP_PORT=8080
DATABASE_URL=sqlite:///./app.db
"""

        elif file_name == "README.md":
            return f"""# {config.project_name}

{description}

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Setup

### Using uv (recommended)

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
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
docker build -t {config.project_name} .

# Run container
docker run -p 8080:8080 {config.project_name}
```

## Kubernetes/Helm

```bash
# Deploy with Helm
helm install {config.project_name} ./k8s -f k8s/values.yaml

# Or apply directly
kubectl apply -f k8s/
```
"""

        elif file_name == "config.py":
            return f'''"""{description} for {config.project_name}."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "{config.project_name}"
    app_env: str = "development"
    app_port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
'''

        # Default for any other file type
        else:
            return f"# {description}\n# TODO: Implement this file\n"
