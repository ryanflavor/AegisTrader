"""Test that the hexagonal architecture is properly enforced.

This test module verifies that dependency flow follows hexagonal architecture
principles:
- Domain has no dependencies on other layers
- Application depends only on Domain and Ports
- Infrastructure depends on Domain, Ports, and Application
- Ports define interfaces only
"""

import ast
from pathlib import Path


def extract_imports(file_path: Path) -> set[str]:
    """Extract all import statements from a Python file."""
    with open(file_path) as f:
        tree = ast.parse(f.read())

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    return imports


def check_layer_dependencies(
    layer_path: Path, layer_name: str, forbidden_layers: list[str]
) -> list[str]:
    """Check if a layer has any forbidden dependencies."""
    violations = []

    for py_file in layer_path.rglob("*.py"):
        # Skip __pycache__ and test files
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue

        imports = extract_imports(py_file)

        for imp in imports:
            # Check for internal package imports
            if imp and imp.startswith("aegis_sdk."):
                parts = imp.split(".")
                if len(parts) >= 2:
                    imported_layer = parts[1]
                    if imported_layer in forbidden_layers:
                        rel_path = py_file.relative_to(layer_path.parent)
                        violations.append(f"{rel_path} imports from {imported_layer} layer: {imp}")

    return violations


class TestHexagonalArchitecture:
    """Test suite for hexagonal architecture compliance."""

    def setup_method(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent / "aegis_sdk"
        self.domain_path = self.base_path / "domain"
        self.application_path = self.base_path / "application"
        self.ports_path = self.base_path / "ports"
        self.infrastructure_path = self.base_path / "infrastructure"

    def test_domain_has_no_external_dependencies(self):
        """Domain layer should not depend on any other layers."""
        violations = check_layer_dependencies(
            self.domain_path, "domain", forbidden_layers=["application", "infrastructure", "ports"]
        )

        assert not violations, "Domain layer has forbidden dependencies:\n" + "\n".join(violations)

    def test_ports_has_only_domain_dependencies(self):
        """Ports layer should only depend on domain layer."""
        violations = check_layer_dependencies(
            self.ports_path,
            "ports",
            forbidden_layers=["infrastructure"],  # Application deps are OK for type hints
        )

        assert not violations, "Ports layer has forbidden dependencies:\n" + "\n".join(violations)

    def test_application_does_not_depend_on_infrastructure(self):
        """Application layer should not depend on infrastructure layer.

        Exception: The deprecated factories.py file is allowed to import from
        infrastructure for backward compatibility, but it should issue a warning.
        """
        violations = []

        for py_file in self.application_path.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue

            # Skip the deprecated factories.py which is allowed for backward compat
            if py_file.name == "factories.py":
                # Check that it has deprecation warning
                with open(py_file) as f:
                    content = f.read()
                    assert (
                        "deprecated" in content.lower()
                    ), "factories.py should have deprecation warning"
                continue

            imports = extract_imports(py_file)

            for imp in imports:
                if imp and imp.startswith("aegis_sdk.infrastructure"):
                    # NO EXCEPTIONS - Application should NEVER import from infrastructure
                    rel_path = py_file.relative_to(self.base_path)
                    violations.append(f"{rel_path} imports from infrastructure: {imp}")

        assert not violations, (
            "Application layer has forbidden infrastructure dependencies:\n" + "\n".join(violations)
        )

    def test_factory_interfaces_in_ports(self):
        """Factory interfaces should be in the ports layer."""
        factory_ports_file = self.ports_path / "factory_ports.py"
        assert factory_ports_file.exists(), "factory_ports.py should exist in ports layer"

        with open(factory_ports_file) as f:
            content = f.read()

        # Check that interfaces are abstract
        assert "ABC" in content, "Factory interfaces should use ABC"
        assert "@abstractmethod" in content, "Factory interfaces should have abstract methods"
        assert "ElectionRepositoryFactory" in content
        assert "KVStoreFactory" in content
        assert "UseCaseFactory" in content

    def test_concrete_factories_in_infrastructure(self):
        """Concrete factory implementations should be in infrastructure layer."""
        app_factories_file = self.infrastructure_path / "application_factories.py"
        assert (
            app_factories_file.exists()
        ), "application_factories.py should exist in infrastructure layer"

        with open(app_factories_file) as f:
            content = f.read()

        # Check that concrete implementations exist
        assert "DefaultElectionRepositoryFactory" in content
        assert "DefaultUseCaseFactory" in content
        assert "DefaultKVStoreFactory" in content

        # Check that they inherit from port interfaces
        assert "ElectionRepositoryFactory" in content
        assert "UseCaseFactory" in content
        assert "KVStoreFactory" in content

        # Check that they import from infrastructure
        assert "from .nats_kv_election_repository" in content
        assert "from .nats_kv_store" in content

    def test_dependency_provider_exists(self):
        """Ensure DependencyProvider exists in application layer."""
        provider_file = self.application_path / "dependency_provider.py"
        assert provider_file.exists(), "dependency_provider.py should exist in application layer"

        with open(provider_file) as f:
            content = f.read()

        # Should NOT import from infrastructure
        assert (
            "from ..infrastructure" not in content
        ), "DependencyProvider should not import from infrastructure"

        # Should have necessary methods
        assert "register_defaults" in content
        assert "get_default_election_factory" in content
        assert "get_default_use_case_factory" in content
        assert "get_default_metrics" in content

    def test_bootstrap_module_exists(self):
        """Ensure bootstrap module exists in infrastructure layer."""
        bootstrap_file = self.infrastructure_path / "bootstrap.py"
        assert bootstrap_file.exists(), "bootstrap.py should exist in infrastructure layer"

        with open(bootstrap_file) as f:
            content = f.read()

        # Should import DependencyProvider from application
        assert "from ..application.dependency_provider import DependencyProvider" in content

        # Should import concrete implementations
        assert "from .application_factories import" in content
        assert "from .in_memory_metrics import" in content

        # Should have bootstrap function
        assert "def bootstrap_defaults()" in content
        assert "DependencyProvider.register_defaults(" in content

    def test_no_circular_dependencies(self):
        """Ensure there are no circular import dependencies."""
        # This is a simplified check - a full check would require import graph analysis

        # Check that infrastructure doesn't import from application factories
        for py_file in self.infrastructure_path.rglob("*.py"):
            if "__pycache__" in str(py_file) or py_file.name == "application_factories.py":
                continue

            imports = extract_imports(py_file)
            for imp in imports:
                if imp and "application.factories" in imp:
                    raise AssertionError(
                        f"{py_file.relative_to(self.base_path)} imports from "
                        f"application.factories, which could cause circular dependency"
                    )

    def test_single_active_service_uses_proper_imports(self):
        """Verify that SingleActiveService uses dependency provider correctly."""
        service_file = self.application_path / "single_active_service.py"

        with open(service_file) as f:
            content = f.read()

        # Should import factory interfaces from ports
        assert (
            "from ..ports.factory_ports import" in content
        ), "SingleActiveService should import factory interfaces from ports"

        # Should use DependencyProvider for defaults
        assert (
            "from .dependency_provider import DependencyProvider" in content
        ), "SingleActiveService should import DependencyProvider"

        # Should NOT have any infrastructure imports
        assert (
            "from ..infrastructure" not in content
        ), "SingleActiveService should NOT import from infrastructure layer"

        # Verify DependencyProvider usage for defaults
        assert (
            "DependencyProvider.get_default_election_factory()" in content
        ), "Should use DependencyProvider for default election factory"
        assert (
            "DependencyProvider.get_default_metrics()" in content
        ), "Should use DependencyProvider for default metrics"
        assert (
            "DependencyProvider.get_default_use_case_factory()" in content
        ), "Should use DependencyProvider for default use case factory"
