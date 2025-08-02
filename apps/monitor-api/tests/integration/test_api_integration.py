"""Integration tests for the FastAPI application.

These tests verify that all layers work together correctly
and that the API endpoints function as expected.
"""

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test the root endpoint returns welcome message."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome to AegisTrader Management Service"}

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test the health check endpoint."""
        # Act
        response = client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "management-service"
        assert data["version"] == "0.1.0"
        assert "nats_url" in data

    def test_ready_endpoint(self, client: TestClient) -> None:
        """Test the readiness check endpoint."""
        # Act
        response = client.get("/ready")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_status_endpoint(self, client: TestClient) -> None:
        """Test the system status endpoint."""
        # Act
        response = client.get("/status")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
        assert data["environment"] in ["development", "staging", "production"]
        assert "deployment_version" in data
        assert data["deployment_version"].startswith("v")

    def test_nonexistent_endpoint_returns_404(self, client: TestClient) -> None:
        """Test that nonexistent endpoints return 404."""
        # Act
        response = client.get("/nonexistent")

        # Assert
        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", ["/health", "/ready", "/status", "/"])
    def test_endpoints_accept_get_only(self, client: TestClient, endpoint: str) -> None:
        """Test that endpoints only accept GET requests."""
        # Act & Assert
        # POST should not be allowed
        response = client.post(endpoint)
        assert response.status_code == 405

        # PUT should not be allowed
        response = client.put(endpoint)
        assert response.status_code == 405

        # DELETE should not be allowed
        response = client.delete(endpoint)
        assert response.status_code == 405

    def test_health_check_detailed_endpoint(self, client: TestClient) -> None:
        """Test the detailed health check endpoint with comprehensive system info."""
        # Act
        response = client.get("/health/detailed")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Check basic health status
        assert data["status"] == "healthy"
        assert data["service"] == "management-service"

        # Check system metrics
        assert "system_metrics" in data
        metrics = data["system_metrics"]
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_usage_percent" in metrics
        assert 0 <= metrics["cpu_percent"] <= 100
        assert 0 <= metrics["memory_percent"] <= 100
        assert 0 <= metrics["disk_usage_percent"] <= 100

        # Check dependencies status
        assert "dependencies" in data
        deps = data["dependencies"]
        assert "nats" in deps
        assert deps["nats"]["status"] in ["healthy", "unhealthy"]
        assert "latency_ms" in deps["nats"]
