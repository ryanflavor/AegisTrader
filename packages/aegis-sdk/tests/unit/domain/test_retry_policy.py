"""Unit tests for RetryPolicy value object."""

import pytest

from aegis_sdk.domain.value_objects import Duration, RetryPolicy


class TestRetryPolicy:
    """Test suite for RetryPolicy value object."""

    def test_default_retry_policy(self):
        """Test default RetryPolicy configuration."""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.initial_delay.seconds == 0.1
        assert policy.backoff_multiplier == 2.0
        assert policy.max_delay.seconds == 5.0
        assert policy.jitter_factor == 0.1
        assert policy.retryable_errors == ["NOT_ACTIVE"]

    def test_custom_retry_policy(self):
        """Test custom RetryPolicy configuration."""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay=Duration(seconds=0.5),
            backoff_multiplier=3.0,
            max_delay=Duration(seconds=10.0),
            jitter_factor=0.2,
            retryable_errors=["NOT_ACTIVE", "ELECTING"],
        )

        assert policy.max_retries == 5
        assert policy.initial_delay.seconds == 0.5
        assert policy.backoff_multiplier == 3.0
        assert policy.max_delay.seconds == 10.0
        assert policy.jitter_factor == 0.2
        assert policy.retryable_errors == ["NOT_ACTIVE", "ELECTING"]

    def test_calculate_delay_first_attempt(self):
        """Test that first attempt has no delay."""
        policy = RetryPolicy()
        delay = policy.calculate_delay(0)
        assert delay.seconds == 0

    def test_calculate_delay_exponential_backoff(self):
        """Test exponential backoff calculation without jitter."""
        policy = RetryPolicy(
            initial_delay=Duration(seconds=1.0),
            backoff_multiplier=2.0,
            max_delay=Duration(seconds=100.0),
            jitter_factor=0.0,  # No jitter for predictable testing
        )

        # First retry: 1 second
        delay1 = policy.calculate_delay(1)
        assert delay1.seconds == 1.0

        # Second retry: 2 seconds
        delay2 = policy.calculate_delay(2)
        assert delay2.seconds == 2.0

        # Third retry: 4 seconds
        delay3 = policy.calculate_delay(3)
        assert delay3.seconds == 4.0

        # Fourth retry: 8 seconds
        delay4 = policy.calculate_delay(4)
        assert delay4.seconds == 8.0

    def test_calculate_delay_respects_max(self):
        """Test that delay is capped at max_delay."""
        policy = RetryPolicy(
            initial_delay=Duration(seconds=1.0),
            backoff_multiplier=10.0,
            max_delay=Duration(seconds=5.0),
            jitter_factor=0.0,
        )

        # Should be capped at 5 seconds
        delay = policy.calculate_delay(10)
        assert delay.seconds == 5.0

    def test_calculate_delay_with_jitter(self):
        """Test that jitter adds randomness to delay."""
        policy = RetryPolicy(
            initial_delay=Duration(seconds=1.0),
            backoff_multiplier=2.0,
            jitter_factor=0.5,  # 50% jitter
        )

        # With 50% jitter, delay should be between 0.5 and 1.5 seconds
        delay = policy.calculate_delay(1)
        assert 0.5 <= delay.seconds <= 1.5

    def test_calculate_delay_invalid_attempt(self):
        """Test that negative attempt number raises error."""
        policy = RetryPolicy()

        with pytest.raises(ValueError, match="Attempt number must be non-negative"):
            policy.calculate_delay(-1)

    def test_should_retry_not_active(self):
        """Test that NOT_ACTIVE errors trigger retry."""
        policy = RetryPolicy()

        assert policy.should_retry("NOT_ACTIVE") is True
        assert policy.should_retry("Instance is NOT_ACTIVE") is True
        assert policy.should_retry("Error: NOT_ACTIVE - standby mode") is True

    def test_should_retry_other_errors(self):
        """Test that other errors don't trigger retry by default."""
        policy = RetryPolicy()

        assert policy.should_retry("TIMEOUT") is False
        assert policy.should_retry("CONNECTION_ERROR") is False
        assert policy.should_retry("UNKNOWN_ERROR") is False
        assert policy.should_retry(None) is False

    def test_should_retry_custom_errors(self):
        """Test custom retryable errors."""
        policy = RetryPolicy(retryable_errors=["NOT_ACTIVE", "ELECTING", "UNAVAILABLE"])

        assert policy.should_retry("NOT_ACTIVE") is True
        assert policy.should_retry("ELECTING") is True
        assert policy.should_retry("Service UNAVAILABLE") is True
        assert policy.should_retry("TIMEOUT") is False

    def test_is_exhausted(self):
        """Test retry exhaustion check."""
        policy = RetryPolicy(max_retries=3)

        assert policy.is_exhausted(0) is False
        assert policy.is_exhausted(1) is False
        assert policy.is_exhausted(2) is False
        assert policy.is_exhausted(3) is True
        assert policy.is_exhausted(4) is True

    def test_no_retries_policy(self):
        """Test policy with no retries allowed."""
        policy = RetryPolicy(max_retries=0)

        assert policy.is_exhausted(0) is True
        assert policy.calculate_delay(0).seconds == 0

    def test_validation_initial_delay_too_small(self):
        """Test that initial delay must be at least 10ms."""
        with pytest.raises(ValueError, match="Initial delay must be at least 10ms"):
            RetryPolicy(initial_delay=Duration(seconds=0.005))

    def test_validation_initial_delay_too_large(self):
        """Test that initial delay must not exceed 10 seconds."""
        with pytest.raises(ValueError, match="Initial delay must not exceed 10 seconds"):
            RetryPolicy(initial_delay=Duration(seconds=15))

    def test_validation_max_delay_greater_than_initial(self):
        """Test that max delay must be greater than initial delay."""
        with pytest.raises(ValueError, match="Max delay must be greater than initial delay"):
            RetryPolicy(
                initial_delay=Duration(seconds=5.0),
                max_delay=Duration(seconds=3.0),
            )

    def test_immutability(self):
        """Test that RetryPolicy is immutable."""
        policy = RetryPolicy()

        # Should not be able to modify attributes
        with pytest.raises(Exception, match="frozen"):  # Pydantic will raise validation error
            policy.max_retries = 10

    def test_retry_policy_equality(self):
        """Test RetryPolicy equality comparison."""
        policy1 = RetryPolicy(max_retries=3)
        policy2 = RetryPolicy(max_retries=3)
        policy3 = RetryPolicy(max_retries=5)

        assert policy1 == policy2
        assert policy1 != policy3

    def test_retry_policy_not_hashable_due_to_list(self):
        """Test that RetryPolicy cannot be hashed due to containing a list.

        This is a known limitation of Pydantic models with list fields.
        RetryPolicy contains retryable_errors which is a list, making it unhashable.
        """
        policy1 = RetryPolicy(max_retries=3)

        # Should raise TypeError when trying to hash
        with pytest.raises(TypeError, match="unhashable type"):
            hash(policy1)

        # Cannot be used in sets
        with pytest.raises(TypeError):
            _ = {policy1}

        # Cannot be used as dict key
        with pytest.raises(TypeError):
            _ = {policy1: "value"}
