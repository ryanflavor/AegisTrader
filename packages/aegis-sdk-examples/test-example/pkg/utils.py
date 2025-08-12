"""Utility functions for test-example."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any


def generate_id(prefix: str = "") -> str:
    """Generate unique ID."""
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}{unique_id}" if prefix else unique_id


def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def serialize_json(obj: Any) -> str:
    """Serialize object to JSON."""

    def default_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)

    return json.dumps(obj, default=default_serializer, indent=2)


def deserialize_json(json_str: str) -> Any:
    """Deserialize JSON string."""
    return json.loads(json_str)


def slugify(text: str) -> str:
    """Convert text to slug format."""
    return text.lower().replace(" ", "-").replace("_", "-")


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split list into chunks."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]
