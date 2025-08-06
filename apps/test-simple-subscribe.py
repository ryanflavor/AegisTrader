#!/usr/bin/env python
"""
Simple test for OpenCTP subscription
"""

import asyncio
import json

import msgpack
from nats.aio.client import Client as NATS


async def test_subscribe():
    """Test direct NATS RPC call"""
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    # Create RPC request
    request = {
        "jsonrpc": "2.0",
        "method": "subscribe",
        "params": {"symbols": ["000001.SZSE", "10008799.SSE", "rb2501.SHFE"]},
        "id": "test-1",
    }

    print(f"Sending request: {json.dumps(request, indent=2)}")

    try:
        # Send RPC request using msgpack
        request_bytes = msgpack.packb(request, use_bin_type=True)
        response = await nc.request("rpc.vnpy-market-demo.subscribe", request_bytes, timeout=5)

        # Try to decode as msgpack first, then json
        try:
            result = msgpack.unpackb(response.data, raw=False)
            print(f"\nReceived msgpack response: {json.dumps(result, indent=2)}")
        except:
            # Try JSON if msgpack fails
            result = json.loads(response.data)
            print(f"\nReceived JSON response: {json.dumps(result, indent=2)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

    await nc.close()


if __name__ == "__main__":
    asyncio.run(test_subscribe())
