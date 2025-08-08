"""Unit tests for infrastructure bootstrap module."""

from unittest.mock import patch

from aegis_sdk.application.dependency_provider import DependencyProvider
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults, reset_defaults


class TestBootstrap:
    """Test the bootstrap functions."""

    def setup_method(self):
        """Reset DependencyProvider before each test."""
        DependencyProvider.reset()

    def teardown_method(self):
        """Clean up after each test."""
        DependencyProvider.reset()

    def test_bootstrap_defaults(self):
        """Test that bootstrap_defaults registers all default implementations."""
        # Verify nothing is registered initially
        assert DependencyProvider._default_election_factory is None
        assert DependencyProvider._default_use_case_factory is None
        assert DependencyProvider._default_kv_store_factory is None
        assert DependencyProvider._default_metrics is None

        # Bootstrap defaults
        bootstrap_defaults()

        # Verify all defaults are now registered
        assert DependencyProvider._default_election_factory is not None
        assert DependencyProvider._default_use_case_factory is not None
        assert DependencyProvider._default_kv_store_factory is not None
        assert DependencyProvider._default_metrics is not None

        # Verify they are the expected types
        from aegis_sdk.infrastructure.application_factories import (
            DefaultElectionRepositoryFactory,
            DefaultKVStoreFactory,
            DefaultUseCaseFactory,
        )
        from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics

        assert isinstance(
            DependencyProvider._default_election_factory, DefaultElectionRepositoryFactory
        )
        assert isinstance(DependencyProvider._default_use_case_factory, DefaultUseCaseFactory)
        assert isinstance(DependencyProvider._default_kv_store_factory, DefaultKVStoreFactory)
        assert DependencyProvider._default_metrics == InMemoryMetrics

    def test_reset_defaults(self):
        """Test that reset_defaults clears all registered defaults."""
        # Bootstrap first
        bootstrap_defaults()

        # Verify defaults are registered
        assert DependencyProvider._default_election_factory is not None
        assert DependencyProvider._default_use_case_factory is not None
        assert DependencyProvider._default_kv_store_factory is not None
        assert DependencyProvider._default_metrics is not None

        # Reset
        reset_defaults()

        # Verify all defaults are cleared
        assert DependencyProvider._default_election_factory is None
        assert DependencyProvider._default_use_case_factory is None
        assert DependencyProvider._default_kv_store_factory is None
        assert DependencyProvider._default_metrics is None

    @patch("aegis_sdk.infrastructure.bootstrap.DependencyProvider.register_defaults")
    def test_bootstrap_calls_register_with_correct_args(self, mock_register):
        """Test that bootstrap_defaults calls register_defaults with correct arguments."""
        bootstrap_defaults()

        # Verify register_defaults was called once
        mock_register.assert_called_once()

        # Get the call arguments
        call_kwargs = mock_register.call_args.kwargs

        # Verify the correct factories are passed
        from aegis_sdk.infrastructure.application_factories import (
            DefaultElectionRepositoryFactory,
            DefaultKVStoreFactory,
            DefaultUseCaseFactory,
        )
        from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics

        assert isinstance(call_kwargs["election_factory"], DefaultElectionRepositoryFactory)
        assert isinstance(call_kwargs["use_case_factory"], DefaultUseCaseFactory)
        assert isinstance(call_kwargs["kv_store_factory"], DefaultKVStoreFactory)
        assert call_kwargs["metrics_class"] == InMemoryMetrics

    @patch("aegis_sdk.infrastructure.bootstrap.DependencyProvider.reset")
    def test_reset_calls_dependency_provider_reset(self, mock_reset):
        """Test that reset_defaults calls DependencyProvider.reset."""
        reset_defaults()
        mock_reset.assert_called_once()

    def test_bootstrap_is_idempotent(self):
        """Test that calling bootstrap_defaults multiple times is safe."""
        # Bootstrap once
        bootstrap_defaults()

        # Get references to the registered factories
        election_factory_1 = DependencyProvider._default_election_factory
        use_case_factory_1 = DependencyProvider._default_use_case_factory
        kv_store_factory_1 = DependencyProvider._default_kv_store_factory
        metrics_class_1 = DependencyProvider._default_metrics

        # Bootstrap again
        bootstrap_defaults()

        # Should have new instances (not the same objects)
        assert DependencyProvider._default_election_factory is not election_factory_1
        assert DependencyProvider._default_use_case_factory is not use_case_factory_1
        assert DependencyProvider._default_kv_store_factory is not kv_store_factory_1
        # Metrics class should be the same class reference
        assert DependencyProvider._default_metrics == metrics_class_1

    def test_get_defaults_after_bootstrap(self):
        """Test that we can retrieve defaults after bootstrapping."""
        bootstrap_defaults()

        # Should be able to get all defaults without errors
        election_factory = DependencyProvider.get_default_election_factory()
        assert election_factory is not None

        use_case_factory = DependencyProvider.get_default_use_case_factory()
        assert use_case_factory is not None

        kv_store_factory = DependencyProvider.get_default_kv_store_factory()
        assert kv_store_factory is not None

        metrics = DependencyProvider.get_default_metrics()
        assert metrics is not None
