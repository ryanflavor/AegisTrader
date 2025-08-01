"""Integration tests for the FastAPI application.

These tests verify that all layers work together correctly
and that the API endpoints function as expected.
"""

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns welcome message."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        assert response.json() == {
            "message": "Welcome to AegisTrader Management Service"
        }

    def test_health_endpoint(self, client):
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

    def test_ready_endpoint(self, client):
        """Test the readiness check endpoint."""
        # Act
        response = client.get("/ready")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_status_endpoint(self, client):
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

    def test_nonexistent_endpoint_returns_404(self, client):
        """Test that nonexistent endpoints return 404."""
        # Act
        response = client.get("/nonexistent")

        # Assert
        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", ["/health", "/ready", "/status", "/"])
    def test_endpoints_accept_get_only(self, client, endpoint):
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
