"""Unit tests for DependencyProvider."""

from unittest.mock import MagicMock

import pytest

from aegis_sdk.application.dependency_provider import DependencyProvider
from aegis_sdk.ports.factory_ports import (
    ElectionRepositoryFactory,
    KVStoreFactory,
    UseCaseFactory,
)
from aegis_sdk.ports.metrics import MetricsPort


class TestDependencyProvider:
    """Test the DependencyProvider class."""

    def setup_method(self):
        """Reset DependencyProvider before each test."""
        DependencyProvider.reset()

    def teardown_method(self):
        """Clean up after each test."""
        DependencyProvider.reset()

    def test_register_defaults_all(self):
        """Test registering all default implementations."""
        # Create mocks
        election_factory = MagicMock(spec=ElectionRepositoryFactory)
        use_case_factory = MagicMock(spec=UseCaseFactory)
        kv_store_factory = MagicMock(spec=KVStoreFactory)
        metrics_class = MagicMock(spec=type[MetricsPort])

        # Register all defaults
        DependencyProvider.register_defaults(
            election_factory=election_factory,
            use_case_factory=use_case_factory,
            kv_store_factory=kv_store_factory,
            metrics_class=metrics_class,
        )

        # Verify all are registered
        assert DependencyProvider._default_election_factory == election_factory
        assert DependencyProvider._default_use_case_factory == use_case_factory
        assert DependencyProvider._default_kv_store_factory == kv_store_factory
        assert DependencyProvider._default_metrics == metrics_class

    def test_register_defaults_partial(self):
        """Test registering only some defaults."""
        election_factory = MagicMock(spec=ElectionRepositoryFactory)

        # Register only election factory
        DependencyProvider.register_defaults(election_factory=election_factory)

        # Verify only election factory is registered
        assert DependencyProvider._default_election_factory == election_factory
        assert DependencyProvider._default_use_case_factory is None
        assert DependencyProvider._default_kv_store_factory is None
        assert DependencyProvider._default_metrics is None

    def test_get_default_election_factory_success(self):
        """Test getting registered election factory."""
        election_factory = MagicMock(spec=ElectionRepositoryFactory)
        DependencyProvider.register_defaults(election_factory=election_factory)

        result = DependencyProvider.get_default_election_factory()
        assert result == election_factory

    def test_get_default_election_factory_not_registered(self):
        """Test getting election factory when not registered."""
        with pytest.raises(RuntimeError, match="No default election factory registered"):
            DependencyProvider.get_default_election_factory()

    def test_get_default_use_case_factory_success(self):
        """Test getting registered use case factory."""
        use_case_factory = MagicMock(spec=UseCaseFactory)
        DependencyProvider.register_defaults(use_case_factory=use_case_factory)

        result = DependencyProvider.get_default_use_case_factory()
        assert result == use_case_factory

    def test_get_default_use_case_factory_not_registered(self):
        """Test getting use case factory when not registered."""
        with pytest.raises(RuntimeError, match="No default use case factory registered"):
            DependencyProvider.get_default_use_case_factory()

    def test_get_default_kv_store_factory_success(self):
        """Test getting registered KV store factory."""
        kv_store_factory = MagicMock(spec=KVStoreFactory)
        DependencyProvider.register_defaults(kv_store_factory=kv_store_factory)

        result = DependencyProvider.get_default_kv_store_factory()
        assert result == kv_store_factory

    def test_get_default_kv_store_factory_not_registered(self):
        """Test getting KV store factory when not registered."""
        with pytest.raises(RuntimeError, match="No default KV store factory registered"):
            DependencyProvider.get_default_kv_store_factory()

    def test_get_default_metrics_success(self):
        """Test getting default metrics instance."""
        # Create a mock metrics class that returns an instance when called
        mock_metrics_instance = MagicMock(spec=MetricsPort)
        metrics_class = MagicMock(spec=type[MetricsPort], return_value=mock_metrics_instance)

        DependencyProvider.register_defaults(metrics_class=metrics_class)

        result = DependencyProvider.get_default_metrics()
        assert result == mock_metrics_instance
        metrics_class.assert_called_once()

    def test_get_default_metrics_not_registered(self):
        """Test getting metrics when not registered."""
        with pytest.raises(RuntimeError, match="No default metrics class registered"):
            DependencyProvider.get_default_metrics()

    def test_reset(self):
        """Test resetting all registered defaults."""
        # Register some defaults
        election_factory = MagicMock(spec=ElectionRepositoryFactory)
        use_case_factory = MagicMock(spec=UseCaseFactory)
        DependencyProvider.register_defaults(
            election_factory=election_factory,
            use_case_factory=use_case_factory,
        )

        # Verify they are registered
        assert DependencyProvider._default_election_factory is not None
        assert DependencyProvider._default_use_case_factory is not None

        # Reset
        DependencyProvider.reset()

        # Verify all are None
        assert DependencyProvider._default_election_factory is None
        assert DependencyProvider._default_use_case_factory is None
        assert DependencyProvider._default_kv_store_factory is None
        assert DependencyProvider._default_metrics is None

    def test_multiple_registrations_overwrite(self):
        """Test that subsequent registrations overwrite previous ones."""
        # First registration
        factory1 = MagicMock(spec=ElectionRepositoryFactory)
        DependencyProvider.register_defaults(election_factory=factory1)
        assert DependencyProvider._default_election_factory == factory1

        # Second registration overwrites
        factory2 = MagicMock(spec=ElectionRepositoryFactory)
        DependencyProvider.register_defaults(election_factory=factory2)
        assert DependencyProvider._default_election_factory == factory2

    def test_register_none_values_ignored(self):
        """Test that None values in register_defaults are ignored."""
        # Set up initial factory
        factory = MagicMock(spec=ElectionRepositoryFactory)
        DependencyProvider.register_defaults(election_factory=factory)

        # Try to overwrite with None - should be ignored
        DependencyProvider.register_defaults(election_factory=None)

        # Original factory should still be there
        assert DependencyProvider._default_election_factory == factory
