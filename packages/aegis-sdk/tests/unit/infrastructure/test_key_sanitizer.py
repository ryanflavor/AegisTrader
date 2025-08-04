"""Tests for key sanitization in infrastructure layer."""

import pytest

from aegis_sdk.infrastructure.key_sanitizer import KeySanitizer


class TestKeySanitizer:
    """Test the KeySanitizer utility."""

    def test_sanitize_valid_key(self):
        """Test sanitizing a key that doesn't need changes."""
        key = "valid_key_123"
        sanitized = KeySanitizer.sanitize(key)
        assert sanitized == key

    def test_sanitize_key_with_spaces(self):
        """Test sanitizing a key with spaces."""
        key = "key with spaces"
        sanitized = KeySanitizer.sanitize(key)
        assert sanitized == "key_with_spaces"

    def test_sanitize_key_with_dots(self):
        """Test sanitizing a key with dots."""
        key = "user.profile.settings"
        sanitized = KeySanitizer.sanitize(key)
        assert sanitized == "user_profile_settings"

    def test_sanitize_key_with_special_chars(self):
        """Test sanitizing a key with various special characters."""
        key = "user:123/profile*settings>data\\test"
        sanitized = KeySanitizer.sanitize(key)
        assert sanitized == "user_123_profile_settings_data_test"

    def test_sanitize_key_with_tabs(self):
        """Test sanitizing a key with tabs."""
        key = "key\twith\ttabs"
        sanitized = KeySanitizer.sanitize(key)
        assert sanitized == "key_with_tabs"

    def test_sanitize_empty_key_raises_error(self):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError, match="Key cannot be empty"):
            KeySanitizer.sanitize("")

        with pytest.raises(ValueError, match="Key cannot be empty"):
            KeySanitizer.sanitize("   ")

    def test_get_invalid_chars(self):
        """Test getting list of invalid characters."""
        invalid = KeySanitizer.get_invalid_chars()
        assert " " in invalid
        assert "\t" in invalid
        assert "." in invalid
        assert "*" in invalid
        assert ">" in invalid
        assert "/" in invalid
        assert "\\" in invalid
        assert ":" in invalid

    def test_is_valid(self):
        """Test checking if a key is valid."""
        assert KeySanitizer.is_valid("valid_key_123")
        assert not KeySanitizer.is_valid("invalid key")
        assert not KeySanitizer.is_valid("user.profile")
        assert not KeySanitizer.is_valid("user:123")

    def test_sanitize_mapping(self):
        """Test creating a mapping between original and sanitized keys."""
        keys = ["valid_key", "key with spaces", "user.profile"]
        mapping = KeySanitizer.create_mapping(keys)

        assert mapping["valid_key"] == "valid_key"
        assert mapping["key with spaces"] == "key_with_spaces"
        assert mapping["user.profile"] == "user_profile"

    def test_sanitize_preserves_uniqueness(self):
        """Test that sanitization preserves key uniqueness where possible."""
        # Different special chars should result in same sanitized key
        key1 = "user.profile"
        key2 = "user/profile"
        key3 = "user profile"

        assert KeySanitizer.sanitize(key1) == "user_profile"
        assert KeySanitizer.sanitize(key2) == "user_profile"
        assert KeySanitizer.sanitize(key3) == "user_profile"

        # This is expected - caller must handle potential collisions
