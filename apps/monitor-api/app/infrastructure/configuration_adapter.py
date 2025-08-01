"""Configuration adapter implementation.

Concrete implementation of the ConfigurationPort interface.
Loads configuration from environment variables.
"""

import os

from ..domain.exceptions import ConfigurationException
from ..domain.models import ServiceConfiguration
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

            nats_url = os.getenv(
                "NATS_URL", f"nats://{default_nats_host}:{default_nats_port}"
            )
            api_port = int(os.getenv("API_PORT", default_api_port))
            log_level = os.getenv("LOG_LEVEL", "INFO").upper()
            environment = os.getenv("ENVIRONMENT", "development").lower()

            # Validate and convert to proper types
            if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                raise ValueError(f"Invalid log level: {log_level}")

            if environment not in ["development", "staging", "production"]:
                raise ValueError(f"Invalid environment: {environment}")

            config = ServiceConfiguration(
                nats_url=nats_url,
                api_port=api_port,
                log_level=log_level,  # type: ignore
                environment=environment,  # type: ignore
            )

            self.validate_configuration(config)
            return config

        except Exception as e:
            raise ConfigurationException(f"Failed to load configuration: {str(e)}")

    def validate_configuration(self, config: ServiceConfiguration) -> None:
        """Validate a configuration object.

        Args:
            config: Configuration to validate

        Raises:
            ConfigurationException: If configuration is invalid
        """
        # Additional validation beyond Pydantic
        if config.api_port < 1024 and os.getuid() != 0:
            raise ConfigurationException(
                f"Port {config.api_port} requires root privileges"
            )

        # In production, ensure we're not using blacklisted NATS hosts
        if config.environment == "production":
            blacklist = os.getenv(
                "PRODUCTION_NATS_HOST_BLACKLIST", "localhost,127.0.0.1"
            ).split(",")
            for host in blacklist:
                if host.strip() in config.nats_url:
                    raise ConfigurationException(
                        f"Production environment should not use {host} in NATS URL"
                    )
