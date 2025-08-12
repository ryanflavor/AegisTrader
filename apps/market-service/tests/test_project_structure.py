"""
Test suite for validating DDD project structure.
These tests ensure the project follows the aegis-sdk-dev DDD template standard.
"""

from pathlib import Path

import pytest


class TestProjectStructure:
    """Validate DDD folder structure according to aegis-sdk-dev template."""

    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        return Path(__file__).parent.parent

    def test_required_ddd_directories_exist(self, project_root):
        """Test that all required DDD directories are present."""
        required_dirs = [
            "app_types",
            "application",
            "crossdomain",
            "domain",
            "infra",
            "tests",
            "pkg",
            "k8s",
        ]

        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists(), f"Required DDD directory '{dir_name}' not found"
            assert dir_path.is_dir(), f"'{dir_name}' exists but is not a directory"

    def test_domain_bounded_contexts_structure(self, project_root):
        """Test that domain bounded contexts are properly structured."""
        domain_contexts = {
            "domain/market_data": "Market Data Context (核心域)",
            "domain/gateway": "Gateway Context (支撑子域)",
            "domain/subscription": "Subscription Context (支撑子域)",
        }

        for context_path, description in domain_contexts.items():
            full_path = project_root / context_path
            assert full_path.exists(), f"Bounded context not found: {description} at {context_path}"
            assert full_path.is_dir(), f"Bounded context is not a directory: {context_path}"

            # Check for __init__.py with documentation
            init_file = full_path / "__init__.py"
            assert init_file.exists(), f"Missing __init__.py in bounded context: {context_path}"

    def test_infrastructure_contexts_structure(self, project_root):
        """Test that infrastructure contexts are properly structured."""
        infra_contexts = {
            "infra/storage": "Storage Context (通用子域)",
            "infra/publishing": "Publishing Context (通用子域)",
        }

        for context_path, description in infra_contexts.items():
            full_path = project_root / context_path
            assert (
                full_path.exists()
            ), f"Infrastructure context not found: {description} at {context_path}"
            assert full_path.is_dir(), f"Infrastructure context is not a directory: {context_path}"

            # Check for __init__.py
            init_file = full_path / "__init__.py"
            assert (
                init_file.exists()
            ), f"Missing __init__.py in infrastructure context: {context_path}"

    def test_domain_shared_components(self, project_root):
        """Test that domain shared components are present."""
        shared_components = ["domain/shared/value_objects.py", "domain/shared/events.py"]

        for component_path in shared_components:
            full_path = project_root / component_path
            assert full_path.exists(), f"Shared domain component not found: {component_path}"
            assert full_path.is_file(), f"Shared component is not a file: {component_path}"

    def test_crossdomain_anti_corruption_layer(self, project_root):
        """Test that Anti-Corruption Layer is properly set up."""
        acl_path = project_root / "crossdomain"
        assert acl_path.exists(), "Anti-Corruption Layer directory not found"

        # Check for expected ACL components
        expected_files = ["anti_corruption.py", "adapters.py", "translators.py"]
        for file_name in expected_files:
            file_path = acl_path / file_name
            assert file_path.exists(), f"ACL component not found: {file_name}"

    def test_application_layer_structure(self, project_root):
        """Test that application layer has proper structure."""
        app_path = project_root / "application"
        assert app_path.exists(), "Application layer directory not found"

        # Check for health service
        health_service = app_path / "health_service.py"
        assert health_service.exists(), "Health service not found in application layer"

    def test_main_entry_point_exists(self, project_root):
        """Test that main.py entry point exists."""
        main_file = project_root / "main.py"
        assert main_file.exists(), "main.py entry point not found"
        assert main_file.is_file(), "main.py is not a file"

    def test_configuration_files_exist(self, project_root):
        """Test that required configuration files are present."""
        config_files = ["pyproject.toml", "Makefile", ".env.example", "Dockerfile", "README.md"]

        for config_file in config_files:
            file_path = project_root / config_file
            assert file_path.exists(), f"Configuration file not found: {config_file}"
            assert file_path.is_file(), f"'{config_file}' is not a file"

    def test_test_structure(self, project_root):
        """Test that test directory structure follows best practices."""
        test_dirs = ["tests/unit", "tests/integration"]

        for test_dir in test_dirs:
            dir_path = project_root / test_dir
            assert dir_path.exists(), f"Test directory not found: {test_dir}"
            assert dir_path.is_dir(), f"'{test_dir}' is not a directory"

        # Check for conftest.py
        conftest = project_root / "tests" / "conftest.py"
        assert conftest.exists(), "tests/conftest.py not found for shared fixtures"
