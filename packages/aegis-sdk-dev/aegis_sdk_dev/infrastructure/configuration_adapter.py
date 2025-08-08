"""Configuration adapter implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class ConfigurationAdapter:
    """Adapter for configuration operations."""

    async def load_configuration(self, path: str) -> dict[str, Any]:
        """Load configuration from the specified path."""
        config_path = Path(path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        try:
            content = config_path.read_text()

            # Determine format based on extension
            if path.endswith((".yaml", ".yml")):
                return yaml.safe_load(content) or {}
            elif path.endswith(".json"):
                return json.loads(content)
            elif path.endswith(".env"):
                return self._parse_env_file(content)
            else:
                # Try to parse as YAML by default
                return yaml.safe_load(content) or {}

        except Exception as e:
            raise ValueError(f"Invalid configuration file {path}: {e}") from e

    async def save_configuration(self, path: str, config: dict[str, Any]) -> None:
        """Save configuration to the specified path."""
        config_path = Path(path)

        try:
            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine format based on extension
            if path.endswith((".yaml", ".yml")):
                content = yaml.dump(config, default_flow_style=False, sort_keys=False)
            elif path.endswith(".json"):
                content = json.dumps(config, indent=2)
            elif path.endswith(".env"):
                content = self._format_env_file(config)
            else:
                # Default to YAML
                content = yaml.dump(config, default_flow_style=False, sort_keys=False)

            config_path.write_text(content)

        except Exception as e:
            raise OSError(f"Unable to save configuration to {path}: {e}") from e

    def validate_configuration(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration structure and values."""
        errors = []

        # Check for required fields
        required_fields = ["service_name"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate service_name
        if "service_name" in config:
            service_name = config["service_name"]
            if not service_name or not isinstance(service_name, str):
                errors.append("service_name must be a non-empty string")
            elif len(service_name) < 3:
                errors.append("service_name must be at least 3 characters long")

        # Validate NATS URL if present
        if "nats_url" in config:
            nats_url = config["nats_url"]
            valid_prefixes = ("nats://", "tls://", "ws://", "wss://")
            if not any(nats_url.startswith(prefix) for prefix in valid_prefixes):
                errors.append(f"Invalid NATS URL format. Must start with one of: {valid_prefixes}")

        # Validate environment if present
        if "environment" in config:
            valid_envs = {
                "auto",
                "local",
                "kubernetes",
                "development",
                "staging",
                "production",
            }
            if config["environment"] not in valid_envs:
                errors.append(f"Invalid environment. Must be one of: {valid_envs}")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _parse_env_file(self, content: str) -> dict[str, Any]:
        """Parse .env file format."""
        config = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    config[key.strip()] = value
        return config

    def _format_env_file(self, config: dict[str, Any]) -> str:
        """Format configuration as .env file."""
        lines = []
        for key, value in config.items():
            # Convert key to uppercase for env vars
            env_key = key.upper().replace("-", "_")
            # Quote value if it contains spaces
            if isinstance(value, str) and " " in value:
                value = f'"{value}"'
            lines.append(f"{env_key}={value}")
        return "\n".join(lines)

    def get_nats_url(self) -> str:
        """Get the NATS URL based on environment."""
        import os

        # Check environment variable first
        nats_url = os.getenv("NATS_URL")
        if nats_url:
            return nats_url

        # Check if we're in Kubernetes
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            return "nats://nats.default.svc.cluster.local:4222"

        # Default to localhost
        return "nats://localhost:4222"

    def get_environment(self) -> str:
        """Get the current environment."""
        import os

        return os.getenv("ENVIRONMENT", "local")
