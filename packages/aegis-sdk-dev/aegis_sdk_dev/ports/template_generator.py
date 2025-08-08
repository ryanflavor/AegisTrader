"""Port interface for template generation."""

from abc import abstractmethod
from typing import Protocol

from aegis_sdk_dev.domain.models import BootstrapConfig


class TemplateGeneratorPort(Protocol):
    """Port interface for generating project template files."""

    @abstractmethod
    def generate_domain_entities(self, config: BootstrapConfig) -> str:
        """Generate domain entities for the project."""
        ...

    @abstractmethod
    def generate_domain_value_objects(self, config: BootstrapConfig) -> str:
        """Generate value objects for the project."""
        ...

    @abstractmethod
    def generate_domain_repositories(self, config: BootstrapConfig) -> str:
        """Generate repository interfaces."""
        ...

    @abstractmethod
    def generate_commands(self, config: BootstrapConfig) -> str:
        """Generate CQRS commands."""
        ...

    @abstractmethod
    def generate_queries(self, config: BootstrapConfig) -> str:
        """Generate CQRS queries."""
        ...

    @abstractmethod
    def generate_handlers(self, config: BootstrapConfig) -> str:
        """Generate command/query handlers."""
        ...

    @abstractmethod
    def generate_infra_init(self, config: BootstrapConfig) -> str:
        """Generate infrastructure init."""
        ...

    @abstractmethod
    def generate_persistence(self, config: BootstrapConfig) -> str:
        """Generate persistence layer."""
        ...

    @abstractmethod
    def generate_messaging(self, config: BootstrapConfig) -> str:
        """Generate messaging layer."""
        ...

    @abstractmethod
    def generate_crossdomain_init(self, config: BootstrapConfig) -> str:
        """Generate crossdomain init."""
        ...

    @abstractmethod
    def generate_translators(self, config: BootstrapConfig) -> str:
        """Generate data translators."""
        ...

    @abstractmethod
    def generate_anti_corruption(self, config: BootstrapConfig) -> str:
        """Generate anti-corruption layer."""
        ...

    @abstractmethod
    def generate_pkg_init(self, config: BootstrapConfig) -> str:
        """Generate pkg init."""
        ...

    @abstractmethod
    def generate_utils(self, config: BootstrapConfig) -> str:
        """Generate utility functions."""
        ...

    @abstractmethod
    def generate_validators(self, config: BootstrapConfig) -> str:
        """Generate validators."""
        ...

    @abstractmethod
    def generate_types_init(self, config: BootstrapConfig) -> str:
        """Generate types init."""
        ...

    @abstractmethod
    def generate_dto(self, config: BootstrapConfig) -> str:
        """Generate DTOs."""
        ...

    @abstractmethod
    def generate_interfaces(self, config: BootstrapConfig) -> str:
        """Generate interfaces."""
        ...
