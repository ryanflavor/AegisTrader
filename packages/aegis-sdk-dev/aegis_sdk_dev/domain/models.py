"""Domain models for aegis-sdk-dev following DDD principles."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ValidationLevel(str, Enum):
    """Value object representing validation issue severity levels."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ProjectTemplate(str, Enum):
    """Value object representing available project templates."""

    ENTERPRISE_DDD = "enterprise_ddd"
    STANDARD = "standard"
    MINIMAL = "minimal"
    MICROSERVICE = "microservice"
    # Legacy templates (for backward compatibility)
    BASIC = "basic"
    SINGLE_ACTIVE = "single_active"
    EVENT_DRIVEN = "event_driven"
    FULL_FEATURED = "full_featured"


class ExecutionType(str, Enum):
    """Value object representing test execution types."""

    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    ALL = "all"


class ValidationIssue(BaseModel):
    """Value object representing a configuration validation issue."""

    level: ValidationLevel = Field(..., description="Issue severity")
    category: str = Field(..., description="Issue category: NATS, K8S, CONFIG, etc.")
    message: str = Field(..., description="Human-readable issue description")
    resolution: str | None = Field(None, description="Suggested resolution steps")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Ensure category is uppercase."""
        return v.upper()

    model_config = {"frozen": True, "strict": True}


class ValidationResult(BaseModel):
    """Aggregate root representing the complete validation result."""

    is_valid: bool = Field(default=True, description="Overall validation status")
    environment: str = Field(..., description="Detected environment")
    issues: list[ValidationIssue] = Field(default_factory=list, description="All validation issues")
    diagnostics: dict[str, Any] = Field(default_factory=dict, description="Diagnostic information")
    recommendations: list[str] = Field(default_factory=list, description="Recommended actions")

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue to the result."""
        self.issues.append(issue)
        if issue.level == ValidationLevel.ERROR:
            self.is_valid = False

    def get_issues_by_level(self, level: ValidationLevel) -> list[ValidationIssue]:
        """Get all issues of a specific level."""
        return [issue for issue in self.issues if issue.level == level]

    def get_issues_by_category(self, category: str) -> list[ValidationIssue]:
        """Get all issues in a specific category."""
        return [issue for issue in self.issues if issue.category == category.upper()]

    def has_errors(self) -> bool:
        """Check if validation has any errors."""
        return any(issue.level == ValidationLevel.ERROR for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if validation has any warnings."""
        return any(issue.level == ValidationLevel.WARNING for issue in self.issues)

    model_config = {"strict": True}


class ServiceConfiguration(BaseModel):
    """Entity representing service configuration."""

    service_name: str = Field(
        ...,
        min_length=3,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Name of the service (alphanumeric and hyphens, min 3 chars)",
    )
    nats_url: str = Field(..., description="NATS connection URL")
    environment: str = Field(default="auto", description="Target environment")
    kv_bucket: str = Field(default="service_registry", description="KV bucket name")
    enable_watchable: bool = Field(default=True, description="Enable watchable discovery")
    debug: bool = Field(default=False, description="Enable debug mode")

    @field_validator("nats_url")
    @classmethod
    def validate_nats_url(cls, v: str) -> str:
        """Validate NATS URL format."""
        valid_prefixes = ("nats://", "tls://", "ws://", "wss://")
        if not v.startswith(valid_prefixes):
            raise ValueError(f"NATS URL must start with one of {valid_prefixes}")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {
            "auto",
            "local",
            "docker",
            "kubernetes",
            "development",
            "staging",
            "production",
        }
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v

    model_config = {"strict": True}


class BootstrapConfig(BaseModel):
    """Value object for bootstrap configuration."""

    project_name: str = Field(..., min_length=1, description="Project name")
    template: ProjectTemplate = Field(..., description="Project template to use")
    service_config: ServiceConfiguration = Field(..., description="Service configuration")
    output_dir: str = Field(default=".", description="Output directory for generated code")
    include_tests: bool = Field(default=True, description="Generate test files")
    include_docker: bool = Field(default=True, description="Generate Dockerfile")
    include_k8s: bool = Field(default=False, description="Generate Kubernetes manifests")

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Validate project name format."""
        import re

        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                "Project name must start with lowercase letter and contain only lowercase letters, numbers, and hyphens"
            )
        return v

    model_config = {"frozen": True, "strict": True}


class RunConfiguration(BaseModel):
    """Value object for test run configuration."""

    test_type: ExecutionType = Field(..., description="Type of tests to run")
    verbose: bool = Field(default=False, description="Verbose output")
    coverage: bool = Field(default=True, description="Generate coverage report")
    min_coverage: float = Field(
        default=80.0, ge=0, le=100, description="Minimum coverage percentage"
    )
    test_path: str = Field(default="tests", description="Path to test directory")
    markers: list[str] = Field(default_factory=list, description="Pytest markers to use")

    model_config = {"frozen": True, "strict": True}


class ExecutionResult(BaseModel):
    """Value object representing test execution results."""

    test_type: ExecutionType = Field(..., description="Type of tests executed")
    passed: int = Field(default=0, ge=0, description="Number of passed tests")
    failed: int = Field(default=0, ge=0, description="Number of failed tests")
    skipped: int = Field(default=0, ge=0, description="Number of skipped tests")
    coverage_percentage: float | None = Field(
        None, ge=0, le=100, description="Test coverage percentage"
    )
    duration_seconds: float = Field(..., ge=0, description="Test execution duration")
    errors: list[str] = Field(default_factory=list, description="Test errors")

    @property
    def total_tests(self) -> int:
        """Get total number of tests."""
        return self.passed + self.failed + self.skipped

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100

    def is_successful(self) -> bool:
        """Check if test run was successful."""
        return self.failed == 0 and len(self.errors) == 0

    model_config = {"frozen": True, "strict": True}
