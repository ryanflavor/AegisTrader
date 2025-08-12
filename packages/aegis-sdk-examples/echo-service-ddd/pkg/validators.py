"""Validators for echo-service-ddd."""

import re


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number."""
    # Remove spaces, dashes, and parentheses
    clean_phone = re.sub(r"[\s\-\(\)]", "", phone)
    pattern = r"^\+?1?\d{9,15}$"
    return bool(re.match(pattern, clean_phone))


def validate_url(url: str) -> bool:
    """Validate URL format."""
    pattern = r"^https?://[\w\-]+(\.[\w\-]+)+[/#?]?.*$"
    return bool(re.match(pattern, url))


def validate_uuid(uuid_str: str) -> bool:
    """Validate UUID format."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    return bool(re.match(pattern, uuid_str, re.IGNORECASE))


def validate_password_strength(password: str) -> str | None:
    """Validate password strength."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return "Password must contain at least one special character"
    return None
