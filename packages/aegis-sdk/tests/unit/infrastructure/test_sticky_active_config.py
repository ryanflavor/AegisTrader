"""Unit tests for StickyActiveConfig."""

import pytest

from aegis_sdk.infrastructure.config import StickyActiveConfig


class TestStickyActiveConfig:
    """Test suite for StickyActiveConfig."""

    def test_default_configuration(self):
        """Test default StickyActiveConfig values."""
        config = StickyActiveConfig()

        assert config.max_retries == 3
        assert config.initial_retry_delay_ms == 100
        assert config.backoff_multiplier == 2.0
        assert config.max_retry_delay_ms == 5000
        assert config.jitter_factor == 0.1
        assert config.enable_metrics is True
        assert config.enable_debug_logging is False
        assert config.failover_timeout_ms == 10000

    def test_custom_configuration(self):
        """Test custom StickyActiveConfig values."""
        config = StickyActiveConfig(
            max_retries=5,
            initial_retry_delay_ms=200,
            backoff_multiplier=3.0,
            max_retry_delay_ms=10000,
            jitter_factor=0.2,
            enable_metrics=False,
            enable_debug_logging=True,
            failover_timeout_ms=30000,
        )

        assert config.max_retries == 5
        assert config.initial_retry_delay_ms == 200
        assert config.backoff_multiplier == 3.0
        assert config.max_retry_delay_ms == 10000
        assert config.jitter_factor == 0.2
        assert config.enable_metrics is False
        assert config.enable_debug_logging is True
        assert config.failover_timeout_ms == 30000

    def test_to_retry_policy(self):
        """Test conversion to RetryPolicy value object."""
        config = StickyActiveConfig(
            max_retries=4,
            initial_retry_delay_ms=150,
            backoff_multiplier=2.5,
            max_retry_delay_ms=8000,
            jitter_factor=0.15,
        )

        retry_policy = config.to_retry_policy()

        assert retry_policy.max_retries == 4
        assert retry_policy.initial_delay.to_milliseconds() == 150
        assert retry_policy.backoff_multiplier == 2.5
        assert retry_policy.max_delay.to_milliseconds() == 8000
        assert retry_policy.jitter_factor == 0.15
        assert retry_policy.retryable_errors == ["NOT_ACTIVE"]

    def test_should_log_debug(self):
        """Test debug logging flag."""
        config_with_debug = StickyActiveConfig(enable_debug_logging=True)
        assert config_with_debug.should_log_debug() is True

        config_without_debug = StickyActiveConfig(enable_debug_logging=False)
        assert config_without_debug.should_log_debug() is False

    def test_should_track_metrics(self):
        """Test metrics tracking flag."""
        config_with_metrics = StickyActiveConfig(enable_metrics=True)
        assert config_with_metrics.should_track_metrics() is True

        config_without_metrics = StickyActiveConfig(enable_metrics=False)
        assert config_without_metrics.should_track_metrics() is False

    def test_validation_max_retries_range(self):
        """Test max_retries validation."""
        # Valid range
        StickyActiveConfig(max_retries=0)
        StickyActiveConfig(max_retries=10)

        # Invalid - too high
        with pytest.raises(ValueError):
            StickyActiveConfig(max_retries=11)

        # Invalid - negative
        with pytest.raises(ValueError):
            StickyActiveConfig(max_retries=-1)

    def test_validation_initial_delay_range(self):
        """Test initial_retry_delay_ms validation."""
        # Valid range
        StickyActiveConfig(initial_retry_delay_ms=10)
        StickyActiveConfig(initial_retry_delay_ms=10000)

        # Invalid - too small
        with pytest.raises(ValueError):
            StickyActiveConfig(initial_retry_delay_ms=9)

        # Invalid - too large
        with pytest.raises(ValueError):
            StickyActiveConfig(initial_retry_delay_ms=10001)

    def test_validation_backoff_multiplier_range(self):
        """Test backoff_multiplier validation."""
        # Valid range
        StickyActiveConfig(backoff_multiplier=1.1)
        StickyActiveConfig(backoff_multiplier=10.0)

        # Invalid - too small
        with pytest.raises(ValueError):
            StickyActiveConfig(backoff_multiplier=1.0)

        # Invalid - too large
        with pytest.raises(ValueError):
            StickyActiveConfig(backoff_multiplier=10.1)

    def test_validation_max_retry_delay_range(self):
        """Test max_retry_delay_ms validation."""
        # Valid range - must be greater than default initial_retry_delay_ms (100)
        StickyActiveConfig(max_retry_delay_ms=101)
        StickyActiveConfig(max_retry_delay_ms=30000)

        # Invalid - too small
        with pytest.raises(ValueError):
            StickyActiveConfig(max_retry_delay_ms=99)

        # Invalid - too large
        with pytest.raises(ValueError):
            StickyActiveConfig(max_retry_delay_ms=30001)

    def test_validation_jitter_factor_range(self):
        """Test jitter_factor validation."""
        # Valid range
        StickyActiveConfig(jitter_factor=0.0)
        StickyActiveConfig(jitter_factor=1.0)

        # Invalid - negative
        with pytest.raises(ValueError):
            StickyActiveConfig(jitter_factor=-0.1)

        # Invalid - too large
        with pytest.raises(ValueError):
            StickyActiveConfig(jitter_factor=1.1)

    def test_validation_failover_timeout_range(self):
        """Test failover_timeout_ms validation."""
        # Valid range
        StickyActiveConfig(failover_timeout_ms=1000)
        StickyActiveConfig(failover_timeout_ms=60000)

        # Invalid - too small
        with pytest.raises(ValueError):
            StickyActiveConfig(failover_timeout_ms=999)

        # Invalid - too large
        with pytest.raises(ValueError):
            StickyActiveConfig(failover_timeout_ms=60001)

    def test_validation_max_delay_greater_than_initial(self):
        """Test that max_retry_delay_ms must be greater than initial_retry_delay_ms."""
        # Valid - max > initial
        StickyActiveConfig(
            initial_retry_delay_ms=100,
            max_retry_delay_ms=1000,
        )

        # Invalid - max <= initial
        with pytest.raises(
            ValueError, match="Max retry delay must be greater than initial retry delay"
        ):
            StickyActiveConfig(
                initial_retry_delay_ms=5000,
                max_retry_delay_ms=5000,
            )

        with pytest.raises(
            ValueError, match="Max retry delay must be greater than initial retry delay"
        ):
            StickyActiveConfig(
                initial_retry_delay_ms=5000,
                max_retry_delay_ms=4000,
            )

    def test_from_dict(self):
        """Test creating StickyActiveConfig from dictionary."""
        config_dict = {
            "max_retries": 4,
            "initial_retry_delay_ms": 200,
            "backoff_multiplier": 2.5,
            "max_retry_delay_ms": 6000,
            "jitter_factor": 0.2,
            "enable_metrics": False,
            "enable_debug_logging": True,
            "failover_timeout_ms": 15000,
        }

        config = StickyActiveConfig(**config_dict)

        assert config.max_retries == 4
        assert config.initial_retry_delay_ms == 200
        assert config.backoff_multiplier == 2.5
        assert config.max_retry_delay_ms == 6000
        assert config.jitter_factor == 0.2
        assert config.enable_metrics is False
        assert config.enable_debug_logging is True
        assert config.failover_timeout_ms == 15000

    def test_to_dict(self):
        """Test converting StickyActiveConfig to dictionary."""
        config = StickyActiveConfig(
            max_retries=4,
            initial_retry_delay_ms=200,
            backoff_multiplier=2.5,
            max_retry_delay_ms=6000,
            jitter_factor=0.2,
            enable_metrics=False,
            enable_debug_logging=True,
            failover_timeout_ms=15000,
        )

        config_dict = config.model_dump()

        assert config_dict["max_retries"] == 4
        assert config_dict["initial_retry_delay_ms"] == 200
        assert config_dict["backoff_multiplier"] == 2.5
        assert config_dict["max_retry_delay_ms"] == 6000
        assert config_dict["jitter_factor"] == 0.2
        assert config_dict["enable_metrics"] is False
        assert config_dict["enable_debug_logging"] is True
        assert config_dict["failover_timeout_ms"] == 15000

    def test_immutability(self):
        """Test that StickyActiveConfig is immutable after creation."""
        config = StickyActiveConfig()

        # Should not be able to modify attributes
        with pytest.raises(Exception, match="frozen"):  # Pydantic will raise validation error
            config.max_retries = 10

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValueError):
            StickyActiveConfig(unknown_field="value")
