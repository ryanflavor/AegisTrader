"""Centralized error handling for the API layer.

This module provides consistent error handling across all API endpoints,
mapping domain exceptions to appropriate HTTP responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...domain.exceptions import (
    ConcurrentUpdateException,
    ConfigurationException,
    DomainException,
    HealthCheckFailedException,
    KVStoreException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
    ServiceUnavailableException,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """Standard error detail model."""

    model_config = ConfigDict(strict=True, frozen=True)

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    model_config = ConfigDict(strict=True, frozen=True)

    error: ErrorDetail = Field(..., description="Error information")


# Mapping of domain exception types to HTTP status codes
EXCEPTION_STATUS_MAP = {
    ServiceNotFoundException: status.HTTP_404_NOT_FOUND,
    ServiceAlreadyExistsException: status.HTTP_409_CONFLICT,
    ConcurrentUpdateException: status.HTTP_409_CONFLICT,
    ServiceUnavailableException: status.HTTP_503_SERVICE_UNAVAILABLE,
    HealthCheckFailedException: status.HTTP_503_SERVICE_UNAVAILABLE,
    ConfigurationException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    KVStoreException: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def create_error_response(
    exception: Exception, status_code: int, details: dict[str, str] | None = None
) -> JSONResponse:
    """Create a standardized error response.

    Args:
        exception: The exception that occurred
        status_code: HTTP status code
        details: Additional error details

    Returns:
        JSONResponse with error information
    """
    if isinstance(exception, DomainException):
        error_code = exception.error_code
        message = exception.message
    else:
        error_code = "INTERNAL_ERROR"
        message = str(exception) or "An internal error occurred"

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=error_code,
            message=message,
            details=details,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Handle domain-specific exceptions.

    Args:
        request: The request that caused the exception
        exc: The domain exception

    Returns:
        JSONResponse with appropriate status code and error details
    """
    logger.warning(
        f"Domain exception on {request.method} {request.url.path}: "
        f"{exc.message} (code: {exc.error_code})"
    )

    # Get status code from mapping
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Extract additional details if available
    details = None
    if hasattr(exc, "__dict__"):
        # For exceptions like ServiceNotFoundException that include the service name
        if hasattr(exc, "message") and "'" in exc.message:
            # Extract service name from message like "Service 'test-service' not found"
            import re

            match = re.search(r"'([^']+)'", exc.message)
            if match:
                details = {"service_name": match.group(1)}

    return create_error_response(exc, status_code, details)


async def validation_exception_handler(
    request: Request, exc: ValidationError | RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation exceptions.

    Args:
        request: The request that caused the exception
        exc: The validation exception

    Returns:
        JSONResponse with validation error details
    """
    # Handle both ValidationError and RequestValidationError
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        error_count = len(errors)
    else:
        errors = exc.errors()
        error_count = exc.error_count()

    logger.warning(f"Validation error on {request.method} {request.url.path}: {error_count} errors")

    # Get the first error for the main message
    first_error = errors[0] if errors else {}

    # Create a more user-friendly error message
    field = ".".join(str(loc) for loc in first_error.get("loc", []))
    error_type = first_error.get("type", "validation_error")
    msg = first_error.get("msg", "Invalid input data")

    # Build details with all validation errors
    details = {
        "field": field,
        "error_type": error_type,
        "errors": [
            {
                "field": ".".join(str(loc) for loc in e.get("loc", [])),
                "message": e.get("msg", ""),
                "type": e.get("type", ""),
            }
            for e in errors
        ],
    }

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message=f"Validation failed for field '{field}': {msg}",
            details=details,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions with consistent format.

    Args:
        request: The request that caused the exception
        exc: The HTTP exception

    Returns:
        JSONResponse with error details
    """
    logger.info(
        f"HTTP exception on {request.method} {request.url.path}: {exc.status_code} - {exc.detail}"
    )

    # If detail is already in our format, use it directly
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )

    # Otherwise, create our standard format
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
        )
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: The request that caused the exception
        exc: The unexpected exception

    Returns:
        JSONResponse with generic error message
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}",
        exc_info=exc,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An internal server error occurred",
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all error handlers with the FastAPI app.

    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(
        RequestValidationError, validation_exception_handler
    )  # Handle FastAPI request validation
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
