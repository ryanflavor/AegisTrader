"""
Test suite for validating project dependencies.
These tests ensure all required dependencies are properly configured in pyproject.toml.
"""

import tomllib
from pathlib import Path

import pytest
from packaging import version


class TestDependencies:
    """Validate that all required dependencies are configured."""

    @pytest.fixture
    def pyproject_data(self):
        """Load and parse pyproject.toml file."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)

    def test_python_version_requirement(self, pyproject_data):
        """Test that Python 3.13+ is required."""
        project_config = pyproject_data.get("project", {})
        requires_python = project_config.get("requires-python", "")

        assert requires_python, "Python version requirement not specified"
        assert "3.13" in requires_python, "Python 3.13+ is required"

    def test_aegis_sdk_dependency(self, pyproject_data):
        """Test that aegis-sdk >= 4.1.0 is configured."""
        dependencies = pyproject_data.get("project", {}).get("dependencies", [])

        # Check if aegis-sdk is in dependencies
        aegis_sdk_found = False
        for dep in dependencies:
            if "aegis-sdk" in dep:
                aegis_sdk_found = True
                # Check version if specified
                if ">=" in dep or "^" in dep:
                    # Extract version number
                    import re

                    version_match = re.search(r"(\d+\.\d+\.\d+)", dep)
                    if version_match:
                        dep_version = version.parse(version_match.group(1))
                        required_version = version.parse("4.1.0")
                        assert (
                            dep_version >= required_version
                        ), f"aegis-sdk version must be >= 4.1.0, found {dep_version}"
                break

        assert aegis_sdk_found, "aegis-sdk dependency not found"

    def test_clickhouse_driver_dependency(self, pyproject_data):
        """Test that clickhouse-driver is configured."""
        dependencies = pyproject_data.get("project", {}).get("dependencies", [])

        clickhouse_found = False
        for dep in dependencies:
            if "clickhouse-driver" in dep:
                clickhouse_found = True
                # Check version if needed
                if "^0.2.6" in dep or ">=0.2.6" in dep:
                    pass  # Version is acceptable
                break

        assert clickhouse_found, "clickhouse-driver dependency not found in pyproject.toml"

    def test_vnpy_dependency(self, pyproject_data):
        """Test that vnpy is configured."""
        dependencies = pyproject_data.get("project", {}).get("dependencies", [])

        vnpy_found = False
        for dep in dependencies:
            if "vnpy" in dep:
                vnpy_found = True
                # Check version if needed
                if "^3.9.0" in dep or ">=3.9.0" in dep:
                    pass  # Version is acceptable
                break

        assert vnpy_found, "vnpy dependency not found in pyproject.toml"

    def test_pydantic_v2_dependency(self, pyproject_data):
        """Test that Pydantic v2 is configured."""
        dependencies = pyproject_data.get("project", {}).get("dependencies", [])

        pydantic_found = False
        for dep in dependencies:
            if "pydantic" in dep and "settings" not in dep:
                pydantic_found = True
                # Ensure it's v2
                assert ">=2" in dep or "^2" in dep, "Pydantic v2 is required"
                break

        assert pydantic_found, "pydantic dependency not found"

    def test_testing_dependencies(self, pyproject_data):
        """Test that testing framework dependencies are configured."""
        # Check in dev dependencies
        dev_deps = pyproject_data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

        required_test_deps = {"pytest": False, "pytest-asyncio": False, "pytest-cov": False}

        for dep in dev_deps:
            for req_dep in required_test_deps:
                if req_dep in dep:
                    required_test_deps[req_dep] = True

        for dep_name, found in required_test_deps.items():
            assert found, f"Testing dependency '{dep_name}' not found in dev dependencies"

    def test_development_tools(self, pyproject_data):
        """Test that development tools are configured."""
        dev_deps = pyproject_data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

        required_tools = {"black": False, "ruff": False, "mypy": False}

        for dep in dev_deps:
            for tool in required_tools:
                if tool in dep:
                    required_tools[tool] = True

        for tool_name, found in required_tools.items():
            assert found, f"Development tool '{tool_name}' not found in dev dependencies"

    def test_tool_configurations(self, pyproject_data):
        """Test that tool configurations are present."""
        tool_config = pyproject_data.get("tool", {})

        # Check ruff configuration
        assert "ruff" in tool_config, "Ruff configuration not found"
        ruff_config = tool_config["ruff"]
        assert ruff_config.get("target-version") == "py313", "Ruff should target Python 3.13"

        # Check black configuration
        assert "black" in tool_config, "Black configuration not found"
        black_config = tool_config["black"]
        assert "py313" in black_config.get("target-version", []), "Black should target Python 3.13"

        # Check mypy configuration
        assert "mypy" in tool_config, "Mypy configuration not found"
        mypy_config = tool_config["mypy"]
        assert mypy_config.get("python_version") == "3.13", "Mypy should target Python 3.13"
        assert mypy_config.get("strict") is True, "Mypy strict mode should be enabled"

        # Check pytest configuration
        assert "pytest" in tool_config, "Pytest configuration not found"

    def test_coverage_configuration(self, pyproject_data):
        """Test that coverage is configured for 80%+ requirement."""
        pytest_config = pyproject_data.get("tool", {}).get("pytest", {}).get("ini_options", {})
        addopts = pytest_config.get("addopts", "")

        assert "--cov" in addopts, "Coverage not configured in pytest"
        assert "--cov-report" in addopts, "Coverage reporting not configured"
