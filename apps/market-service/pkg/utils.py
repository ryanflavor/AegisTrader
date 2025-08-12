"""Utility functions for market-service.

⚠️ IMPORTANT: The AegisSDK handles ALL serialization automatically!
- DO NOT implement JSON/msgpack serialization - SDK does this
- DO NOT implement datetime handling for messages - SDK does this
- Use SDK's built-in serialization for all NATS messages

The SDK uses msgpack by default for efficiency. External services
should never need to handle serialization details.
"""

import hashlib
import uuid
from typing import Any

# ⚠️ WARNING: Do not add JSON serialization functions here!
# The SDK handles all message serialization automatically.
# If you need to serialize for non-NATS purposes (like file storage),
# consider using the SDK's serialization utilities instead.


def generate_id(prefix: str = "") -> str:
    """Generate unique ID for entities."""
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}{unique_id}" if prefix else unique_id


def hash_password(password: str) -> str:
    """Hash password using SHA256.

    Note: For production, use proper password hashing like bcrypt.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def slugify(text: str) -> str:
    """Convert text to slug format for URLs or identifiers."""
    return text.lower().replace(" ", "-").replace("_", "-")


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split list into chunks for batch processing."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def generate_cache_key(*args) -> str:
    """Generate cache key from arguments."""
    return ":".join(str(arg) for arg in args)


# ⚠️ REMINDER: For any RPC or message passing, the SDK handles serialization!
# You should work with native Python objects and let the SDK convert them.
