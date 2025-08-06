#!/usr/bin/env python
"""
Direct test for OpenCTP subscription
"""

import asyncio
import sys

from aegis_sdk import Service
from aegis_sdk.domain.models import RPCRequest
from aegis_sdk.infrastructure import NATSAdapter
from dotenv import load_dotenv
from loguru import logger


async def test_subscribe():
    """Test subscription directly"""
    # Load env
    load_dotenv(".env.openctp")

    # Setup logging
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # Connect to NATS
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])
    logger.info("Connected to NATS")

    # Create a minimal service to make RPC calls
    service = Service("test-direct", adapter)
    await service.start()

    # Test subscription with different symbol formats
    test_cases = [
        # Single symbol
        {"symbols": ["000001.SZSE"]},
        # Multiple symbols
        {"symbols": ["000001.SZSE", "10008799.SSE", "rb2501.SHFE"]},
        # Test just the problematic symbol
        {"symbols": ["10008799.SSE"]},
    ]

    for i, params in enumerate(test_cases):
        logger.info(f"\n=== Test Case {i + 1}: {params} ===")

        request = RPCRequest(target="vnpy-market-demo", method="subscribe", params=params)

        try:
            result = await service.call_rpc(request)
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback

            traceback.print_exc()

        await asyncio.sleep(1)

    # Cleanup
    await service.stop()
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(test_subscribe())
