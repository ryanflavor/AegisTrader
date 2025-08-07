"""Unit tests for BootstrapService following TDD principles."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from aegis_sdk_dev.application.bootstrap_service import BootstrapService
from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ProjectTemplate,
)


class TestBootstrapService:
    """Test BootstrapService application service."""

    @pytest.fixture
    def mock_console(self) -> MagicMock:
        """Create mock console port."""
        mock = MagicMock()
        mock.print = MagicMock()
        mock.print_error = MagicMock()
        mock.print_success = MagicMock()
        mock.print_warning = MagicMock()
        return mock

    @pytest.fixture
    def mock_environment(self) -> MagicMock:
        """Create mock environment port."""
        mock = MagicMock()
        mock.detect_environment = MagicMock(return_value="local")
        mock.get = MagicMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_nats(self) -> AsyncMock:
        """Create mock NATS connection port."""
        mock = AsyncMock()
        mock.connect = AsyncMock(return_value=True)
        mock.disconnect = AsyncMock()
        mock.is_connected = AsyncMock(return_value=True)
        mock.bucket_exists = AsyncMock(return_value=True)
        mock.create_kv_bucket = AsyncMock()
        return mock

    @pytest.fixture
    def bootstrap_service(
        self, mock_console: MagicMock, mock_environment: MagicMock, mock_nats: AsyncMock
    ) -> BootstrapService:
        """Create BootstrapService instance with mocked dependencies."""
        return BootstrapService(
            console=mock_console,
            environment=mock_environment,
            nats=mock_nats,
        )

    @pytest.mark.asyncio
    async def test_bootstrap_sdk_service_success(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_environment: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test successful SDK service bootstrap."""
        # Arrange
        service_name = "test-service"
        nats_url = "nats://localhost:4222"
        kv_bucket = "test_registry"

        # Act
        result = await bootstrap_service.bootstrap_sdk_service(
            service_name=service_name,
            nats_url=nats_url,
            kv_bucket=kv_bucket,
            enable_watchable=True,
        )

        # Assert
        assert result["service_name"] == service_name
        assert result["nats_url"] == nats_url
        assert result["kv_bucket"] == kv_bucket
        assert result["environment"] == "local"
        assert result["enable_watchable"] is True
        assert result["connected"] is True

        # Verify interactions
        mock_environment.detect_environment.assert_called_once()
        mock_nats.connect.assert_called_once_with(nats_url)
        mock_nats.bucket_exists.assert_called_once_with(kv_bucket)
        mock_console.print_success.assert_called()

    @pytest.mark.asyncio
    async def test_bootstrap_sdk_service_connection_failure(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test SDK service bootstrap with NATS connection failure."""
        # Arrange
        mock_nats.connect.return_value = False
        service_name = "test-service"
        nats_url = "nats://localhost:4222"

        # Act & Assert
        with pytest.raises(ConnectionError, match="Failed to connect to NATS"):
            await bootstrap_service.bootstrap_sdk_service(
                service_name=service_name,
                nats_url=nats_url,
            )

        # Verify error was logged
        mock_console.print_error.assert_called()

    @pytest.mark.asyncio
    async def test_bootstrap_sdk_service_connection_exception(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test SDK service bootstrap with NATS connection exception."""
        # Arrange
        mock_nats.connect.side_effect = Exception("Network error")
        service_name = "test-service"
        nats_url = "nats://localhost:4222"

        # Act & Assert
        with pytest.raises(Exception, match="Network error"):
            await bootstrap_service.bootstrap_sdk_service(
                service_name=service_name,
                nats_url=nats_url,
            )

        # Verify error was logged
        mock_console.print_error.assert_called_with("Failed to connect to NATS: Network error")

    @pytest.mark.asyncio
    async def test_bootstrap_sdk_service_creates_bucket(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test SDK service bootstrap creates KV bucket when it doesn't exist."""
        # Arrange
        mock_nats.bucket_exists.return_value = False
        service_name = "test-service"
        nats_url = "nats://localhost:4222"
        kv_bucket = "new_bucket"

        # Act
        result = await bootstrap_service.bootstrap_sdk_service(
            service_name=service_name,
            nats_url=nats_url,
            kv_bucket=kv_bucket,
        )

        # Assert
        assert result["kv_bucket"] == kv_bucket
        mock_nats.create_kv_bucket.assert_called_once_with(kv_bucket)
        mock_console.print.assert_any_call(f"Creating KV bucket: {kv_bucket}")

    def test_create_bootstrap_config_basic(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test creating basic bootstrap configuration."""
        # Arrange
        project_name = "test-project"
        template = "basic"
        nats_url = "nats://localhost:4222"

        # Act
        config = bootstrap_service.create_bootstrap_config(
            project_name=project_name,
            template=template,
            nats_url=nats_url,
        )

        # Assert
        assert isinstance(config, BootstrapConfig)
        assert config.project_name == project_name
        assert config.template == ProjectTemplate.BASIC
        assert config.service_config.service_name == project_name
        assert config.service_config.nats_url == nats_url
        assert config.output_dir == "."
        assert config.include_tests is True
        assert config.include_docker is True
        assert config.include_k8s is False

    def test_create_bootstrap_config_with_options(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test creating bootstrap configuration with custom options."""
        # Arrange
        project_name = "custom-project"
        template = "full_featured"
        nats_url = "nats://custom:4222"
        output_dir = "/custom/path"

        # Act
        config = bootstrap_service.create_bootstrap_config(
            project_name=project_name,
            template=template,
            nats_url=nats_url,
            output_dir=output_dir,
            environment="kubernetes",
            kv_bucket="custom_registry",
            enable_watchable=False,
            debug=True,
            include_tests=False,
            include_docker=False,
            include_k8s=True,
        )

        # Assert
        assert config.project_name == project_name
        assert config.template == ProjectTemplate.FULL_FEATURED
        assert config.service_config.environment == "kubernetes"
        assert config.service_config.kv_bucket == "custom_registry"
        assert config.service_config.enable_watchable is False
        assert config.service_config.debug is True
        assert config.output_dir == output_dir
        assert config.include_tests is False
        assert config.include_docker is False
        assert config.include_k8s is True

    def test_create_bootstrap_config_invalid_template(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test creating bootstrap configuration with invalid template."""
        # Arrange
        project_name = "test-project"
        template = "invalid_template"

        # Act & Assert
        with pytest.raises(ValueError):
            bootstrap_service.create_bootstrap_config(
                project_name=project_name,
                template=template,
            )

        # Verify error was logged
        mock_console.print_error.assert_called_with(f"Invalid template: {template}")

    def test_create_bootstrap_config_all_templates(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test creating bootstrap configuration with all valid templates."""
        # Arrange
        project_name = "test-project"
        templates = ["basic", "single_active", "event_driven", "full_featured"]

        # Act & Assert
        for template in templates:
            config = bootstrap_service.create_bootstrap_config(
                project_name=project_name,
                template=template,
            )
            assert config.template == ProjectTemplate(template)

    @pytest.mark.asyncio
    async def test_cleanup_service_connected(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test cleaning up service when NATS is connected."""
        # Arrange
        service_name = "test-service"
        mock_nats.is_connected.return_value = True

        # Act
        await bootstrap_service.cleanup_service(service_name)

        # Assert
        mock_nats.disconnect.assert_called_once()
        mock_console.print.assert_any_call(f"Cleaning up service: {service_name}")
        mock_console.print.assert_any_call("Disconnected from NATS")
        mock_console.print_success.assert_called_with(
            f"Service {service_name} cleaned up successfully"
        )

    @pytest.mark.asyncio
    async def test_cleanup_service_not_connected(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test cleaning up service when NATS is not connected."""
        # Arrange
        service_name = "test-service"
        mock_nats.is_connected.return_value = False

        # Act
        await bootstrap_service.cleanup_service(service_name)

        # Assert
        mock_nats.disconnect.assert_not_called()
        mock_console.print_success.assert_called_with(
            f"Service {service_name} cleaned up successfully"
        )

    @pytest.mark.asyncio
    async def test_bootstrap_sdk_service_environment_detection(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
        mock_environment: MagicMock,
        mock_nats: AsyncMock,
    ):
        """Test SDK service bootstrap with different environment detections."""
        # Arrange
        environments = ["local", "kubernetes", "docker", "production"]
        service_name = "test-service"
        nats_url = "nats://localhost:4222"

        # Act & Assert
        for env in environments:
            mock_environment.detect_environment.return_value = env
            result = await bootstrap_service.bootstrap_sdk_service(
                service_name=service_name,
                nats_url=nats_url,
            )
            assert result["environment"] == env
            mock_console.print.assert_any_call(f"Detected environment: {env}")

    def test_create_bootstrap_config_validates_service_name(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test bootstrap configuration validates service name."""
        # Arrange - invalid service names
        invalid_names = ["", "a", "ab", "test@service", "test service"]

        # Act & Assert
        for name in invalid_names:
            with pytest.raises(ValidationError):
                bootstrap_service.create_bootstrap_config(
                    project_name=name,
                    template="basic",
                )

    def test_create_bootstrap_config_validates_nats_url(
        self,
        bootstrap_service: BootstrapService,
        mock_console: MagicMock,
    ):
        """Test bootstrap configuration validates NATS URL."""
        # Arrange - invalid NATS URLs
        invalid_urls = ["http://localhost:4222", "localhost:4222", "invalid-url"]

        # Act & Assert
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                bootstrap_service.create_bootstrap_config(
                    project_name="test-project",
                    template="basic",
                    nats_url=url,
                )
