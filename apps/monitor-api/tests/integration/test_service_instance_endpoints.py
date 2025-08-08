"""Integration tests for service instance endpoints.

These tests verify the complete request/response cycle for service instance
endpoints, ensuring proper integration between layers.
"""

import json
from datetime import UTC, datetime

import pytest
from app.domain.models import ServiceInstance
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def sample_instances():
    """Create sample service instances for testing."""
    now = datetime.now(UTC).isoformat()
    return [
        ServiceInstance(
            service_name="order-service",
            instance_id="order-01",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=now,
            metadata={"region": "us-east-1"},
        ),
        ServiceInstance(
            service_name="order-service",
            instance_id="order-02",
            version="1.0.0",
            status="ACTIVE",
            last_heartbeat=now,
            metadata={"region": "us-west-2"},
        ),
        ServiceInstance(
            service_name="pricing-service",
            instance_id="pricing-01",
            version="2.0.0",
            status="UNHEALTHY",
            last_heartbeat=now,
        ),
        ServiceInstance(
            service_name="risk-service",
            instance_id="risk-01",
            version="1.5.0",
            status="STANDBY",
            last_heartbeat=now,
        ),
    ]


class TestServiceInstanceEndpoints:
    """Test cases for service instance API endpoints."""

    def test_list_all_instances(self, mock_kv_store, sample_instances):
        """Test GET /api/instances endpoint."""
        # Arrange
        mock_kv_store.keys.return_value = [
            f"service-instances.{inst.service_name}.{inst.instance_id}" for inst in sample_instances
        ]

        # Create mock entries
        entries = []
        for inst in sample_instances:
            entry = type("Entry", (), {})()
            entry.value = json.dumps(inst.model_dump()).encode()
            entries.append(entry)

        mock_kv_store.get.side_effect = entries

        # Act
        with TestClient(app) as client:
            response = client.get("/api/instances")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert all(isinstance(inst, dict) for inst in data)

    def test_list_instances_by_service(self, mock_kv_store, sample_instances):
        """Test GET /api/instances/{service_name} endpoint."""
        # Arrange
        service_name = "order-service"
        order_instances = [inst for inst in sample_instances if inst.service_name == service_name]

        mock_kv_store.keys.return_value = [
            f"service-instances.{inst.service_name}.{inst.instance_id}" for inst in order_instances
        ]

        entries = []
        for inst in order_instances:
            entry = type("Entry", (), {})()
            entry.value = json.dumps(inst.model_dump()).encode()
            entries.append(entry)

        mock_kv_store.get.side_effect = entries

        # Act
        with TestClient(app) as client:
            response = client.get(f"/api/instances/{service_name}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(inst["service_name"] == service_name for inst in data)

    def test_get_specific_instance(self, mock_kv_store, sample_instances):
        """Test GET /api/instances/{service_name}/{instance_id} endpoint."""
        # Arrange
        service_name = "order-service"
        instance_id = "order-01"
        instance = next(
            inst
            for inst in sample_instances
            if inst.service_name == service_name and inst.instance_id == instance_id
        )

        entry = type("Entry", (), {})()
        entry.value = json.dumps(instance.model_dump()).encode()
        mock_kv_store.get.return_value = entry

        # Act
        with TestClient(app) as client:
            response = client.get(f"/api/instances/{service_name}/{instance_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["service_name"] == service_name
        assert data["instance_id"] == instance_id
        assert data["version"] == "1.0.0"
        assert data["status"] == "ACTIVE"

    def test_get_instance_not_found(self, mock_kv_store):
        """Test GET /api/instances/{service_name}/{instance_id} with non-existent instance."""
        # Arrange
        mock_kv_store.get.return_value = None

        # Act
        with TestClient(app) as client:
            response = client.get("/api/instances/unknown-service/unknown-id")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_health_summary(self, mock_kv_store, sample_instances):
        """Test GET /api/instances/health/summary endpoint."""
        # Arrange
        mock_kv_store.keys.return_value = [
            f"service-instances.{inst.service_name}.{inst.instance_id}" for inst in sample_instances
        ]

        entries = []
        for inst in sample_instances:
            entry = type("Entry", (), {})()
            entry.value = json.dumps(inst.model_dump()).encode()
            entries.append(entry)

        mock_kv_store.get.side_effect = entries

        # Act
        with TestClient(app) as client:
            response = client.get("/api/instances/health/summary")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["active"] == 2
        assert data["unhealthy"] == 1
        assert data["standby"] == 1

    def test_get_instances_by_status(self, mock_kv_store, sample_instances):
        """Test GET /api/instances/status/{status} endpoint."""
        # Arrange
        status = "ACTIVE"
        mock_kv_store.keys.return_value = [
            f"service-instances.{inst.service_name}.{inst.instance_id}" for inst in sample_instances
        ]

        entries = []
        for inst in sample_instances:
            entry = type("Entry", (), {})()
            entry.value = json.dumps(inst.model_dump()).encode()
            entries.append(entry)

        mock_kv_store.get.side_effect = entries

        # Act
        with TestClient(app) as client:
            response = client.get(f"/api/instances/status/{status}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(inst["status"] == status for inst in data)

    def test_get_instances_by_invalid_status(self):
        """Test GET /api/instances/status/{status} with invalid status."""
        # Act
        with TestClient(app) as client:
            response = client.get("/api/instances/status/INVALID")

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "Invalid status" in data["detail"]

    def test_error_handling(self, mock_kv_store):
        """Test proper error handling when KV store fails."""
        # Arrange
        mock_kv_store.keys.side_effect = Exception("Connection failed")

        # Act
        with TestClient(app) as client:
            response = client.get("/api/instances")

        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "Failed to list service instances" in data["detail"]
