"""Data Transfer Objects for Single Active Service with Pydantic v2 strict validation.

This module defines DTOs with comprehensive validation for the single active service pattern.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SingleActiveConfig(BaseModel):
    """Configuration DTO for SingleActiveService with strict validation."""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    # Service configuration
    service_name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Name of the service",
    )
    instance_id: str | None = Field(
        default=None,
        max_length=256,
        description="Instance identifier (auto-generated if not provided)",
    )
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Service version in semantic versioning format",
    )

    # Registry configuration
    registry_ttl: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="TTL for registry entries in seconds",
    )
    heartbeat_interval: int = Field(
        default=10,
        ge=1,
        le=300,
        description="Heartbeat interval in seconds",
    )
    enable_registration: bool = Field(
        default=True,
        description="Whether to enable service registration",
    )

    # Sticky active configuration
    group_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        description="Sticky active group identifier",
    )
    leader_ttl_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="TTL for leader key in seconds",
    )

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name format."""
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9-_.]*$", v):
            raise ValueError(
                f"Invalid service name: {v}. Must start with a letter and contain only "
                "letters, numbers, hyphens, underscores, and dots."
            )
        return v

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, v: str) -> str:
        """Validate group ID format."""
        import re

        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-_.]*$", v):
            raise ValueError(
                f"Invalid group ID: {v}. Must start with alphanumeric and contain only "
                "letters, numbers, hyphens, underscores, and dots."
            )
        return v

    @field_validator("heartbeat_interval")
    @classmethod
    def validate_heartbeat_interval(cls, v: int, info) -> int:
        """Validate heartbeat interval is less than registry TTL."""
        if "registry_ttl" in info.data:
            registry_ttl = info.data["registry_ttl"]
            if v >= registry_ttl:
                raise ValueError(
                    f"Heartbeat interval ({v}s) must be less than registry TTL ({registry_ttl}s)"
                )
        return v

    @field_validator("leader_ttl_seconds")
    @classmethod
    def validate_leader_ttl(cls, v: int, info) -> int:
        """Validate leader TTL is reasonable compared to heartbeat."""
        if "heartbeat_interval" in info.data:
            heartbeat = info.data["heartbeat_interval"]
            if v > heartbeat:
                raise ValueError(
                    f"Leader TTL ({v}s) should not exceed heartbeat interval ({heartbeat}s)"
                )
        return v


class ExclusiveRPCResponse(BaseModel):
    """Response model for exclusive RPC calls."""

    model_config = ConfigDict(strict=True)

    success: bool = Field(..., description="Whether the RPC was successful")
    error: str | None = Field(default=None, description="Error code if failed")
    message: str | None = Field(default=None, description="Error message if failed")
    result: dict[str, Any] | None = Field(default=None, description="Result data if successful")


class SingleActiveStatus(BaseModel):
    """Status information for a single active service instance."""

    model_config = ConfigDict(strict=True)

    service_name: str = Field(..., description="Name of the service")
    instance_id: str = Field(..., description="Instance identifier")
    group_id: str = Field(..., description="Sticky active group")
    is_active: bool = Field(..., description="Whether this instance is active")
    is_leader: bool = Field(..., description="Whether this instance is the leader")
    leader_instance_id: str | None = Field(
        default=None,
        description="ID of the current leader instance",
    )
    last_heartbeat: str | None = Field(
        default=None,
        description="ISO timestamp of last heartbeat",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
