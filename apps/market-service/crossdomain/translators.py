"""
Data translators for market-service.

Translates between external formats and domain models.
"""

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


class MarketDataTranslator(Translator):
    """Translates market data between formats."""

    def translate(self, source: dict) -> dict:
        """Translate external market data to domain format."""
        return {
            "symbol": source.get("symbol") or source.get("ticker"),
            "exchange": source.get("exchange") or source.get("market"),
            "price": source.get("last_price") or source.get("price"),
            "volume": source.get("volume") or source.get("qty"),
            "timestamp": source.get("timestamp") or source.get("time"),
        }

    def reverse_translate(self, source: dict) -> dict:
        """Translate domain market data to external format."""
        return {
            "ticker": source.get("symbol"),
            "market": source.get("exchange"),
            "last_price": source.get("price"),
            "qty": source.get("volume"),
            "time": source.get("timestamp"),
        }
