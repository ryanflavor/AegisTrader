"""Data Transfer Objects for echo-service-ddd."""

from datetime import datetime

from pydantic import BaseModel, Field


class BaseDTO(BaseModel):
    """Base DTO class."""

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UserDTO(BaseDTO):
    """User data transfer object."""

    id: str = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    email: str = Field(..., description="User email")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Update timestamp")


class CreateUserDTO(BaseDTO):
    """Create user request DTO."""

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class UpdateUserDTO(BaseDTO):
    """Update user request DTO."""

    name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class UserListDTO(BaseDTO):
    """User list response DTO."""

    users: list[UserDTO]
    total: int
    page: int = 1
    page_size: int = 10


class ErrorDTO(BaseDTO):
    """Error response DTO."""

    error_code: str
    message: str
    details: dict | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
