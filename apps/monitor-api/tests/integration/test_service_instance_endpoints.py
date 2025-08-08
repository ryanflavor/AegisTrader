"""Integration tests for service instance endpoints.

These tests verify the complete request/response cycle for service instance
endpoints with real NATS integration. The tests are designed to work with
the actual K8s environment where echo-service instances are running.
"""

from collections.abc import Generator

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def test_client() -> Generator[TestClient]:
    """Create a test client for the app.

    The TestClient will handle the app's lifespan events (startup/shutdown),
    which includes initializing the connection manager.
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture
def is_real_nats_available(test_client: TestClient) -> bool:
    """Check if real NATS is available and connected."""
    try:
        response = test_client.get("/health")
        return response.status_code == 200 and "nats://" in response.json().get("nats_url", "")
    except Exception:
        return False


class TestServiceInstanceEndpoints:
    """Test cases for service instance API endpoints with real NATS integration."""

    def test_list_all_instances(self, test_client: TestClient, is_real_nats_available: bool):
        """Test GET /api/instances endpoint with real data."""
        # Act
        response = test_client.get("/api/instances")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # With real NATS, we should have at least the echo-service instances
        if is_real_nats_available:
            # We expect 3 echo-service instances from the K8s deployment
            echo_instances = [inst for inst in data if inst.get("serviceName") == "echo-service"]
            assert len(echo_instances) >= 1, "Should have at least one echo-service instance"

            # Verify instance structure
            for inst in data:
                assert "serviceName" in inst
                assert "instanceId" in inst
                assert "version" in inst
                assert "status" in inst
                assert "lastHeartbeat" in inst
        else:
            # If no real NATS, the list might be empty or have test data
            assert isinstance(data, list)

    def test_list_instances_by_service(self, test_client: TestClient, is_real_nats_available: bool):
        """Test GET /api/instances/{service_name} endpoint with real data."""
        # Test with echo-service which should exist in the real environment
        service_name = "echo-service"

        # Act
        response = test_client.get(f"/api/instances/{service_name}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        if is_real_nats_available:
            # Should return echo-service instances
            assert len(data) >= 1, "Should have at least one echo-service instance"
            assert all(inst["serviceName"] == service_name for inst in data)
        else:
            # Empty list if service doesn't exist
            assert isinstance(data, list)

        # Test with non-existent service
        response = test_client.get("/api/instances/non-existent-service")
        assert response.status_code == 200
        data = response.json()
        assert data == []  # Should return empty list for non-existent service

    def test_get_specific_instance(self, test_client: TestClient, is_real_nats_available: bool):
        """Test GET /api/instances/{service_name}/{instance_id} endpoint with real data."""
        if is_real_nats_available:
            # First, get the list of echo-service instances to find a real instance ID
            response = test_client.get("/api/instances/echo-service")
            instances = response.json()

            if instances:
                # Use the first real instance for testing
                real_instance = instances[0]
                service_name = real_instance["serviceName"]
                instance_id = real_instance["instanceId"]

                # Act
                response = test_client.get(f"/api/instances/{service_name}/{instance_id}")

                # Assert
                assert response.status_code == 200
                data = response.json()
                assert data["serviceName"] == service_name
                assert data["instanceId"] == instance_id
                assert "version" in data
                assert "status" in data
                assert data["status"] in ["ACTIVE", "STANDBY", "UNHEALTHY"]

        # Test with non-existent instance (should return 404)
        response = test_client.get("/api/instances/non-existent-service/non-existent-id")
        assert response.status_code == 404

    def test_get_instance_not_found(self, test_client: TestClient):
        """Test GET /api/instances/{service_name}/{instance_id} with non-existent instance."""
        # Act - Try to get a non-existent instance
        response = test_client.get("/api/instances/unknown-service/unknown-id")

        # Assert
        assert response.status_code == 404
        data = response.json()
        # The error format can vary - check both old and new formats
        if "detail" in data:
            assert "not found" in data["detail"].lower() or "failed" in data["detail"].lower()
        elif "error" in data:
            # New error format with structured error object
            error = data["error"]
            assert "message" in error
            assert "not found" in error["message"].lower()

    def test_get_health_summary(self, test_client: TestClient, is_real_nats_available: bool):
        """Test GET /api/instances/health/summary endpoint with real data."""
        # Act
        response = test_client.get("/api/instances/health/summary")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify the structure of the health summary
        assert "total" in data
        assert "active" in data
        assert "unhealthy" in data
        assert "standby" in data

        # Total should be the sum of all status counts
        total = data["total"]
        status_sum = data["active"] + data["unhealthy"] + data["standby"]
        assert total == status_sum

        if is_real_nats_available:
            # With real NATS and echo-service running, we should have at least some active instances
            assert data["total"] >= 1
            assert data["active"] >= 1  # Echo-service instances should be active

    def test_get_instances_by_status(self, test_client: TestClient, is_real_nats_available: bool):
        """Test GET /api/instances/status/{status} endpoint with real data."""
        # Test with ACTIVE status (echo-service instances should be active)
        status = "ACTIVE"

        # Act
        response = test_client.get(f"/api/instances/status/{status}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        if is_real_nats_available:
            # Should have at least the echo-service instances which are ACTIVE
            assert len(data) >= 1
            assert all(inst["status"] == status for inst in data)
        else:
            # Should return a list (possibly empty)
            assert isinstance(data, list)

        # Test other valid statuses
        for status in ["STANDBY", "UNHEALTHY"]:
            response = test_client.get(f"/api/instances/status/{status}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            # All returned instances should have the requested status
            assert all(inst["status"] == status for inst in data)

    def test_get_instances_by_invalid_status(self, test_client: TestClient):
        """Test GET /api/instances/status/{status} with invalid status."""
        # Act
        response = test_client.get("/api/instances/status/INVALID_STATUS")

        # Assert
        # The endpoint should either return 400 for invalid status or 200 with empty list
        # depending on implementation
        if response.status_code == 400:
            data = response.json()
            # Check both old and new error formats
            if "detail" in data:
                assert "invalid" in data["detail"].lower() or "status" in data["detail"].lower()
            elif "error" in data:
                # New error format with structured error object
                error = data["error"]
                assert "message" in error
                assert "invalid" in error["message"].lower() or "status" in error["message"].lower()
        else:
            # Some implementations may just return empty list for unknown status
            assert response.status_code == 200
            data = response.json()
            assert data == []

    def test_error_handling(self, test_client: TestClient):
        """Test proper error handling for various error conditions."""
        # Test with malformed service name (if validation exists)
        response = test_client.get("/api/instances/../../etc/passwd")
        # Should either sanitize or reject
        assert response.status_code in [200, 400, 404]

        # Test with extremely long service name
        long_name = "a" * 1000
        response = test_client.get(f"/api/instances/{long_name}")
        assert response.status_code in [200, 400, 404]

        # If response is 200, should return empty list
        if response.status_code == 200:
            data = response.json()
            assert data == []
