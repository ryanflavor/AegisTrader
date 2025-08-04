"""Tests for adapters module."""

from unittest.mock import AsyncMock

import pytest
from order_service.adapters import RemotePricingServiceAdapter


class TestRemotePricingServiceAdapter:
    """Test cases for RemotePricingServiceAdapter."""

    async def test_get_price_success(self):
        """Test successful price retrieval."""
        # Mock service
        mock_service = AsyncMock()
        mock_service.call_rpc = AsyncMock(return_value={"price": 150.25})

        # Create adapter
        adapter = RemotePricingServiceAdapter(mock_service)

        # Test get_price
        price = await adapter.get_price("AAPL")

        assert price == 150.25
        mock_service.call_rpc.assert_called_once_with(
            "pricing-service", "get_price", {"symbol": "AAPL"}
        )

    async def test_get_price_default_on_failure(self):
        """Test price retrieval returns default on failure."""
        # Mock service to raise exception
        mock_service = AsyncMock()
        mock_service.call_rpc = AsyncMock(side_effect=Exception("Service error"))

        # Create adapter
        adapter = RemotePricingServiceAdapter(mock_service)

        # Test get_price should return default
        price = await adapter.get_price("AAPL")
        assert price == 100.0

    async def test_get_price_no_discovery(self):
        """Test price retrieval when discovery is not available."""
        # Mock service without discovery
        mock_service = AsyncMock()

        # Create adapter with no discovery
        adapter = RemotePricingServiceAdapter(mock_service, discovery=None)
        adapter._discovery = None

        # Test get_price should raise RuntimeError
        with pytest.raises(RuntimeError, match="Service discovery not available"):
            await adapter.get_price("AAPL")
