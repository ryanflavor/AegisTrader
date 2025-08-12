"""Data translators for market-service."""

from abc import ABC, abstractmethod
from typing import Any


class Translator(ABC):
    """Base translator class."""

    @abstractmethod
    def translate(self, source: Any) -> Any:
        """Translate from external to internal format."""
        pass

    @abstractmethod
    def reverse_translate(self, source: Any) -> Any:
        """Translate from internal to external format."""
        pass


class ExternalAPITranslator(Translator):
    """Translates external API responses."""

    def translate(self, source: dict) -> dict:
        """Translate external API response to domain model."""
        return {
            "id": source.get("external_id"),
            "name": source.get("display_name"),
            "email": source.get("email_address"),
            "created_at": source.get("registration_date"),
        }

    def reverse_translate(self, source: dict) -> dict:
        """Translate domain model to external API format."""
        return {
            "external_id": source.get("id"),
            "display_name": source.get("name"),
            "email_address": source.get("email"),
            "registration_date": source.get("created_at"),
        }


class LegacySystemTranslator(Translator):
    """Translates legacy system data."""

    def translate(self, source: str) -> dict:
        """Parse legacy format to domain model."""
        # Example: "ID:123|NAME:John|EMAIL:john@example.com"
        parts = source.split("|")
        data = {}
        for part in parts:
            key, value = part.split(":")
            data[key.lower()] = value
        return data

    def reverse_translate(self, source: dict) -> str:
        """Convert domain model to legacy format."""
        parts = []
        for key, value in source.items():
            parts.append(f"{key.upper()}:{value}")
        return "|".join(parts)
