"""Integration tests for the Service Registry API.

These tests use testcontainers to spin up a real NATS instance
and test all CRUD operations end-to-end.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

import httpx
import pytest
from testcontainers.compose import DockerCompose

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

# Test data
TEST_SERVICE_1 = {
    "service_name": "payment-service",
    "owner": "payments-team",
    "description": "Handles payment processing",
    "version": "1.0.0",
}

TEST_SERVICE_2 = {
    "service_name": "notification-service",
    "owner": "platform-team",
    "description": "Sends notifications to users",
    "version": "2.1.0",
}

INVALID_SERVICE_NAMES = [
    "Payment-Service",  # Uppercase not allowed
    "p",  # Too short
    "payment_service",  # Underscore not allowed
    "123-payment",  # Must start with letter
    "payment-" * 10 + "service",  # Too long
]


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def docker_compose() -> Generator[DockerCompose]:
    """Start NATS using docker-compose for integration tests."""
    # Use the project's docker-compose.yaml
    compose_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "docker-compose.yaml"
    )
    compose = DockerCompose(compose_path)

    # Start only NATS service
    compose.start()

    # Wait for NATS to be ready
    time.sleep(5)

    yield compose

    compose.stop()


@pytest.fixture
async def api_client(docker_compose) -> AsyncGenerator[httpx.AsyncClient]:
    """Create an async HTTP client for testing the API."""
    # Set environment variables for the test
    os.environ["NATS_URL"] = "nats://localhost:4222"
    os.environ["API_PORT"] = "8001"
    os.environ["LOG_LEVEL"] = "INFO"
    os.environ["ENVIRONMENT"] = "development"

    # Import and run the FastAPI app
    from app.main import app
    from uvicorn import Config, Server

    config = Config(app=app, host="127.0.0.1", port=8001, log_level="info")
    server = Server(config)

    # Run server in background
    task = asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(2)

    # Create client
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        yield client

    # Cleanup
    server.should_exit = True
    await task


@pytest.fixture
async def clean_kv_store(api_client: httpx.AsyncClient):
    """Clean the KV store before each test."""
    # List all services
    response = await api_client.get("/api/services")
    services = response.json()

    # Delete all existing services
    for service in services:
        await api_client.delete(f"/api/services/{service['service_name']}")


class TestServiceRegistryAPI:
    """Test suite for Service Registry API."""

    @pytest.mark.asyncio
    async def test_list_empty_services(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test listing services when registry is empty."""
        response = await api_client.get("/api/services")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_service_success(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test creating a new service successfully."""
        response = await api_client.post("/api/services", json=TEST_SERVICE_1)
        assert response.status_code == 201
        assert "Location" in response.headers
        assert response.headers["Location"] == "/api/services/payment-service"

        data = response.json()
        assert data["service_name"] == TEST_SERVICE_1["service_name"]
        assert data["owner"] == TEST_SERVICE_1["owner"]
        assert data["description"] == TEST_SERVICE_1["description"]
        assert data["version"] == TEST_SERVICE_1["version"]
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] == data["updated_at"]

    @pytest.mark.asyncio
    async def test_create_duplicate_service(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test creating a duplicate service returns 409."""
        # Create first service
        response = await api_client.post("/api/services", json=TEST_SERVICE_1)
        assert response.status_code == 201

        # Try to create duplicate
        response = await api_client.post("/api/services", json=TEST_SERVICE_1)
        assert response.status_code == 409
        error = response.json()
        assert error["error"]["code"] == "SERVICE_ALREADY_EXISTS"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_name", INVALID_SERVICE_NAMES)
    async def test_create_service_invalid_name(
        self, api_client: httpx.AsyncClient, clean_kv_store, invalid_name: str
    ):
        """Test creating service with invalid name patterns."""
        service = TEST_SERVICE_1.copy()
        service["service_name"] = invalid_name

        response = await api_client.post("/api/services", json=service)
        assert response.status_code == 422
        error = response.json()
        assert error["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_get_service_success(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test getting an existing service."""
        # Create service
        await api_client.post("/api/services", json=TEST_SERVICE_1)

        # Get service
        response = await api_client.get("/api/services/payment-service")
        assert response.status_code == 200

        data = response.json()
        assert data["service_name"] == TEST_SERVICE_1["service_name"]
        assert data["owner"] == TEST_SERVICE_1["owner"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_service(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test getting a non-existent service returns 404."""
        response = await api_client.get("/api/services/nonexistent-service")
        assert response.status_code == 404
        error = response.json()
        assert error["error"]["code"] == "SERVICE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_service_success(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test updating an existing service."""
        # Create service
        create_response = await api_client.post("/api/services", json=TEST_SERVICE_1)
        created_service = create_response.json()
        created_at = created_service["created_at"]

        # Wait a bit to ensure timestamp difference
        await asyncio.sleep(0.1)

        # Update service
        updates = {
            "description": "Updated payment processing service",
            "version": "1.1.0",
        }
        response = await api_client.put("/api/services/payment-service", json=updates)
        assert response.status_code == 200

        data = response.json()
        assert data["service_name"] == TEST_SERVICE_1["service_name"]
        assert data["owner"] == TEST_SERVICE_1["owner"]  # Unchanged
        assert data["description"] == updates["description"]
        assert data["version"] == updates["version"]
        assert data["created_at"] == created_at
        assert data["updated_at"] > created_at

    @pytest.mark.asyncio
    async def test_update_with_optimistic_locking(
        self, api_client: httpx.AsyncClient, clean_kv_store
    ):
        """Test optimistic locking with revision."""
        # Create service
        await api_client.post("/api/services", json=TEST_SERVICE_1)

        # Get service with revision
        response = await api_client.get("/api/services/payment-service/revision")
        assert response.status_code == 200
        data = response.json()
        revision = data["revision"]

        # Update with correct revision
        updates = {"version": "1.1.0", "revision": revision}
        response = await api_client.put("/api/services/payment-service", json=updates)
        assert response.status_code == 200

        # Try to update with old revision (should fail)
        updates = {"version": "1.2.0", "revision": revision}
        response = await api_client.put("/api/services/payment-service", json=updates)
        assert response.status_code == 409
        error = response.json()
        assert error["error"]["code"] == "CONCURRENT_UPDATE"

    @pytest.mark.asyncio
    async def test_delete_service_success(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test deleting an existing service."""
        # Create service
        await api_client.post("/api/services", json=TEST_SERVICE_1)

        # Delete service
        response = await api_client.delete("/api/services/payment-service")
        assert response.status_code == 204

        # Verify it's gone
        response = await api_client.get("/api/services/payment-service")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_service(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test deleting a non-existent service returns 404."""
        response = await api_client.delete("/api/services/nonexistent-service")
        assert response.status_code == 404
        error = response.json()
        assert error["error"]["code"] == "SERVICE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_multiple_services(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test listing multiple services."""
        # Create multiple services
        await api_client.post("/api/services", json=TEST_SERVICE_1)
        await api_client.post("/api/services", json=TEST_SERVICE_2)

        # List services
        response = await api_client.get("/api/services")
        assert response.status_code == 200
        services = response.json()
        assert len(services) == 2

        # Check service names
        service_names = {s["service_name"] for s in services}
        assert "payment-service" in service_names
        assert "notification-service" in service_names

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test handling concurrent requests."""
        # Create services concurrently
        tasks = [
            api_client.post("/api/services", json=TEST_SERVICE_1),
            api_client.post("/api/services", json=TEST_SERVICE_2),
        ]
        responses = await asyncio.gather(*tasks)

        # Both should succeed
        assert all(r.status_code == 201 for r in responses)

        # List to verify
        response = await api_client.get("/api/services")
        assert len(response.json()) == 2

    @pytest.mark.asyncio
    async def test_field_validation(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test field validation rules."""
        test_cases = [
            # Owner too long
            {
                **TEST_SERVICE_1,
                "owner": "a" * 101,
            },
            # Description too long
            {
                **TEST_SERVICE_1,
                "description": "a" * 501,
            },
            # Invalid version format
            {
                **TEST_SERVICE_1,
                "version": "1.0",
            },
            # Missing required field
            {
                "service_name": "test-service",
                "owner": "test-team",
                "description": "Test service",
                # version missing
            },
        ]

        for invalid_service in test_cases:
            response = await api_client.post("/api/services", json=invalid_service)
            assert response.status_code == 422
            error = response.json()
            assert error["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_health_check_with_services(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test that health check still works with service registry."""
        # Create a service
        await api_client.post("/api/services", json=TEST_SERVICE_1)

        # Health check should still work
        response = await api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_performance_requirements(self, api_client: httpx.AsyncClient, clean_kv_store):
        """Test performance requirements (< 100ms for single operations)."""
        # Create service and measure time
        start = time.time()
        response = await api_client.post("/api/services", json=TEST_SERVICE_1)
        create_time = (time.time() - start) * 1000
        assert response.status_code == 201
        assert create_time < 100  # Should be less than 100ms

        # Get service and measure time
        start = time.time()
        response = await api_client.get("/api/services/payment-service")
        get_time = (time.time() - start) * 1000
        assert response.status_code == 200
        assert get_time < 100  # Should be less than 100ms
