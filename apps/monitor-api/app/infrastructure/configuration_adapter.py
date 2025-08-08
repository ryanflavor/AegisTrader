"""Configuration adapter implementation.

Concrete implementation of the ConfigurationPort interface.
Loads configuration from environment variables.
"""

from __future__ import annotations

import os
from typing import Literal, cast

from ..domain.exceptions import ConfigurationException
from ..domain.models import ServiceConfiguration, ValidationIssue, ValidationLevel, ValidationResult
from ..ports.configuration import ConfigurationPort


class EnvironmentConfigurationAdapter(ConfigurationPort):
    """Adapter that loads configuration from environment variables."""

    def load_configuration(self) -> ServiceConfiguration:
        """Load service configuration from environment variables.

        Returns:
            ServiceConfiguration: Validated configuration

        Raises:
            ConfigurationException: If configuration is invalid
        """
        try:
            # Get defaults from environment
            default_nats_host = os.getenv("DEFAULT_NATS_HOST", "localhost")
            default_nats_port = os.getenv("NATS_CLIENT_PORT", "4222")
            default_api_port = os.getenv("API_CONTAINER_PORT", "8100")

            nats_url = os.getenv("NATS_URL", f"nats://{default_nats_host}:{default_nats_port}")
            api_port = int(os.getenv("API_PORT", default_api_port))
            log_level = os.getenv("LOG_LEVEL", "INFO").upper()
            environment = os.getenv("ENVIRONMENT", "development").lower()
            stale_threshold_seconds = int(os.getenv("STALE_THRESHOLD_SECONDS", "35"))

            # Validate and convert to proper types
            if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                raise ValueError(f"Invalid log level: {log_level}")

            if environment not in ["development", "staging", "production"]:
                raise ValueError(f"Invalid environment: {environment}")

            if stale_threshold_seconds < 1 or stale_threshold_seconds > 300:
                raise ValueError(
                    f"Invalid stale threshold: {stale_threshold_seconds} (must be 1-300)"
                )

            config = ServiceConfiguration(
                nats_url=nats_url,
                api_port=api_port,
                log_level=cast(Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], log_level),
                environment=cast(Literal["development", "staging", "production"], environment),
                stale_threshold_seconds=stale_threshold_seconds,
            )

            validation_result = self.validate_configuration(config)
            if not validation_result.is_valid:
                error_messages = [
                    issue.message
                    for issue in validation_result.get_issues_by_level(ValidationLevel.ERROR)
                ]
                raise ConfigurationException(
                    f"Configuration validation failed: {'; '.join(error_messages)}"
                )
            return config

        except Exception as e:
            raise ConfigurationException(f"Failed to load configuration: {str(e)}") from e

    def validate_configuration(self, config: ServiceConfiguration) -> ValidationResult:
        """Validate a configuration object.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult: Result with validation status and any issues
        """
        result = ValidationResult(context="ServiceConfiguration")

        # Check port privileges
        if config.api_port < 1024 and os.getuid() != 0:
            result.add_issue(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="CONFIG",
                    message=f"Port {config.api_port} requires root privileges",
                    resolution="Use a port >= 1024 or run with root privileges",
                    details={"port": config.api_port, "uid": os.getuid()},
                )
            )

        # In production, ensure we're not using blacklisted NATS hosts
        if config.environment == "production":
            blacklist = os.getenv("PRODUCTION_NATS_HOST_BLACKLIST", "localhost,127.0.0.1").split(
                ","
            )
            for host in blacklist:
                if host.strip() in config.nats_url:
                    result.add_issue(
                        ValidationIssue(
                            level=ValidationLevel.ERROR,
                            category="CONFIG",
                            message=f"Production environment should not use {host} in NATS URL",
                            resolution="Use a proper production NATS server URL",
                            details={"host": host, "nats_url": config.nats_url},
                        )
                    )

        # Add diagnostic information
        result.diagnostics["environment"] = config.environment
        result.diagnostics["nats_url"] = config.nats_url
        result.diagnostics["api_port"] = config.api_port

        return result
