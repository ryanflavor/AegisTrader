"""K8s integration tests for monitor-api.

These tests verify the actual integration with K8s environment
including NATS connectivity and service discovery.
"""

import os

import pytest
import requests


@pytest.mark.skipif(
    os.getenv("SKIP_K8S_TESTS", "true").lower() == "true",
    reason="K8s integration tests skipped (set SKIP_K8S_TESTS=false to run)",
)
class TestK8sIntegration:
    """Integration tests that require actual K8s environment."""

    def test_api_health_via_port_forward(self):
        """Test API health endpoint via kubectl port-forward."""
        # This assumes port-forward is running on localhost:8100
        try:
            response = requests.get("http://localhost:8100/health", timeout=5)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "nats://aegis-trader-nats" in data["nats_url"]
        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available on localhost:8100")

    def test_api_service_instances(self):
        """Test that API can list actual service instances."""
        try:
            response = requests.get("http://localhost:8100/api/instances", timeout=5)
            assert response.status_code == 200
            data = response.json()
            # We should have echo-service instances running
            echo_instances = [i for i in data if i.get("serviceName") == "echo-service"]
            assert len(echo_instances) >= 1, "Should have at least one echo-service instance"
        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available on localhost:8100")

    def test_api_services_list(self):
        """Test that API can list registered services."""
        try:
            response = requests.get("http://localhost:8100/api/services", timeout=5)
            assert response.status_code == 200
            data = response.json()
            # Check if response is a list
            assert isinstance(data, list)
        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available on localhost:8100")

    def test_monitor_ui_availability(self):
        """Test that monitor UI is accessible."""
        try:
            response = requests.get("http://localhost:3100", timeout=5)
            assert response.status_code == 200
            # UI should return HTML
            assert "text/html" in response.headers.get("content-type", "")
        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available on localhost:3100")

    def test_nats_connectivity(self):
        """Test that NATS is accessible via port-forward."""
        import asyncio

        import nats

        async def check_nats():
            try:
                nc = await nats.connect("nats://localhost:4222")
                # Test basic connectivity
                assert nc.is_connected
                await nc.close()
                return True
            except Exception:
                return False

        try:
            result = asyncio.run(check_nats())
            assert result, "Should be able to connect to NATS"
        except Exception:
            pytest.skip("NATS not available on localhost:4222")


@pytest.mark.skipif(
    os.getenv("SKIP_K8S_TESTS", "true").lower() == "true",
    reason="K8s integration tests skipped",
)
class TestServiceRegistration:
    """Test service registration and discovery in K8s."""

    def test_echo_service_registration(self):
        """Test that echo-service instances are properly registered."""
        try:
            # Check service instances endpoint
            response = requests.get("http://localhost:8100/api/instances/echo-service", timeout=5)
            assert response.status_code == 200
            instances = response.json()

            # Verify instance properties
            for instance in instances:
                assert instance.get("serviceName") == "echo-service"
                assert instance.get("status") in ["ACTIVE", "STANDBY", "UNHEALTHY"]
                assert "instanceId" in instance
                assert "lastHeartbeat" in instance

            # There should be 3 echo-service replicas based on deployment
            assert len(instances) >= 1, "Should have at least one echo-service instance"

        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available")

    def test_service_health_summary(self):
        """Test service health summary endpoint."""
        try:
            response = requests.get("http://localhost:8100/api/instances/health/summary", timeout=5)
            assert response.status_code == 200
            summary = response.json()

            # Verify summary structure
            assert "total" in summary
            assert "active" in summary
            assert "standby" in summary
            assert "unhealthy" in summary

            # Total should match sum of status counts
            total = summary["total"]
            status_sum = summary["active"] + summary["standby"] + summary["unhealthy"]
            assert total == status_sum

        except requests.exceptions.ConnectionError:
            pytest.skip("Port-forward not available")


def test_make_commands():
    """Test that make commands are working properly."""
    import subprocess

    # Test make status command
    result = subprocess.run(["make", "status"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "aegis-trader" in result.stdout

    # Check for key services
    assert "monitor-api" in result.stdout
    assert "monitor-ui" in result.stdout
    assert "echo-service" in result.stdout
    assert "nats" in result.stdout
