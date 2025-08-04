"""Key sanitization utility for NATS compatibility.

This module provides utilities for sanitizing keys to be compatible with
NATS KV store requirements. This is an infrastructure concern, not a domain concern.
"""

from typing import ClassVar


class KeySanitizer:
    """Utility class for sanitizing keys for NATS KV store.

    NATS KV keys cannot contain: spaces, tabs, '.', '*', '>', '/', '\\', ':'
    This class provides methods to sanitize keys by replacing invalid characters.
    """

    # NATS invalid characters
    INVALID_CHARS: ClassVar[list[str]] = [" ", "\t", ".", "*", ">", "/", "\\", ":"]
    REPLACEMENT_CHAR: ClassVar[str] = "_"

    @classmethod
    def sanitize(cls, key: str) -> str:
        """Sanitize a key for NATS compatibility.

        Args:
            key: The original key

        Returns:
            Sanitized key with invalid characters replaced

        Raises:
            ValueError: If the key is empty or only whitespace
        """
        if not key.strip():
            raise ValueError("Key cannot be empty or contain only whitespace")

        sanitized = key
        for char in cls.INVALID_CHARS:
            sanitized = sanitized.replace(char, cls.REPLACEMENT_CHAR)

        return sanitized

    @classmethod
    def is_valid(cls, key: str) -> bool:
        """Check if a key is valid for NATS without sanitization.

        Args:
            key: The key to check

        Returns:
            True if the key contains no invalid characters
        """
        return not any(char in key for char in cls.INVALID_CHARS)

    @classmethod
    def get_invalid_chars(cls) -> list[str]:
        """Get the list of invalid characters.

        Returns:
            List of characters that are invalid in NATS keys
        """
        return cls.INVALID_CHARS.copy()

    @classmethod
    def create_mapping(cls, keys: list[str]) -> dict[str, str]:
        """Create a mapping of original keys to sanitized keys.

        Args:
            keys: List of original keys

        Returns:
            Dictionary mapping original keys to sanitized keys

        Note:
            This method does not check for collisions. If multiple original
            keys sanitize to the same value, the mapping will contain duplicates.
            Callers should handle potential collisions appropriately.
        """
        return {key: cls.sanitize(key) for key in keys}
