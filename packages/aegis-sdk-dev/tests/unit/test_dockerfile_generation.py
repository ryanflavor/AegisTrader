"""Test Dockerfile generation improvements."""

from aegis_sdk_dev.domain.models import BootstrapConfig, ProjectTemplate, ServiceConfiguration
from aegis_sdk_dev.domain.simple_project_generator import SimpleProjectGenerator


class TestDockerfileGeneration:
    """Test Dockerfile template generation."""

    def test_dockerfile_includes_proxy_args(self):
        """Test that Dockerfile includes proxy ARG declarations."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content("Dockerfile", "Docker image definition", config)

        # Check for proxy ARG declarations
        assert "ARG HTTP_PROXY" in content
        assert "ARG HTTPS_PROXY" in content
        assert "ARG NO_PROXY" in content

        # Check for proxy usage in RUN commands
        assert 'if [ -n "$HTTP_PROXY" ]' in content
        assert "export http_proxy=$HTTP_PROXY" in content
        assert "export UV_HTTP_PROXY=$HTTP_PROXY" in content

    def test_dockerfile_uses_python_313(self):
        """Test that Dockerfile uses Python 3.13."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content("Dockerfile", "Docker image definition", config)

        assert "FROM python:3.13-slim" in content

    def test_dockerfile_includes_healthcheck(self):
        """Test that Dockerfile includes HEALTHCHECK."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content("Dockerfile", "Docker image definition", config)

        assert "HEALTHCHECK" in content
        assert "--interval=30s" in content

    def test_dockerfile_uses_main_py(self):
        """Test that Dockerfile uses main.py as entry point."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content("Dockerfile", "Docker image definition", config)

        assert 'CMD ["python", "main.py"]' in content

    def test_docker_compose_includes_nats(self):
        """Test that docker-compose.yml includes NATS service."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content(
            "docker-compose.yml", "Docker Compose configuration", config
        )

        # Check NATS service configuration
        assert "nats:" in content
        assert "image: nats:latest" in content
        assert '"-js -m 8222"' in content
        assert "healthcheck:" in content

        # Check proxy args in build
        assert "HTTP_PROXY: ${HTTP_PROXY}" in content
        assert "HTTPS_PROXY: ${HTTPS_PROXY}" in content
        assert "NO_PROXY: ${NO_PROXY}" in content

    def test_main_py_is_runnable(self):
        """Test that main.py template is a runnable entry point."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content("main.py", "Application entry point", config)

        # Check for async main function
        assert "async def main() -> None:" in content
        assert "asyncio.run(main())" in content

        # Check for signal handling
        assert "signal.signal(signal.SIGTERM" in content
        assert "signal.signal(signal.SIGINT" in content

        # Check for environment variable usage
        assert 'os.getenv("SERVICE_NAME"' in content
        assert 'os.getenv("NATS_URL"' in content
        assert 'os.getenv("LOG_LEVEL"' in content

    def test_env_example_includes_proxy_settings(self):
        """Test that .env.example includes proxy configuration."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content(
            ".env.example", "Environment variables example", config
        )

        # Check for proxy settings section
        assert "# Docker build proxy configuration" in content
        assert "# HTTP_PROXY=" in content
        assert "# HTTPS_PROXY=" in content
        assert "# NO_PROXY=" in content

        # Check for NATS configuration
        assert "NATS_URL=nats://localhost:4222" in content
        assert "NATS_CLIENT_PORT=4222" in content

    def test_pyproject_includes_aegis_sdk_comment(self):
        """Test that pyproject.toml includes note about aegis-sdk."""
        generator = SimpleProjectGenerator()
        config = BootstrapConfig(
            project_name="test-service",
            template=ProjectTemplate.ENTERPRISE_DDD,
            output_dir=".",
            service_config=ServiceConfiguration(
                service_name="test-service",
                nats_url="nats://localhost:4222",
                environment="local",
            ),
        )

        content = generator._generate_file_content(
            "pyproject.toml", "Project configuration", config
        )

        # Check for aegis-sdk note
        assert "# Note: aegis-sdk should be installed separately" in content
        assert 'description = "AegisSDK service: test-service"' in content
        assert "httpx>=0.24.0" in content
