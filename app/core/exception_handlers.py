import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.exceptions import BitenexException, ValidationError
from app.shared import ErrorResponse
from app.shared.dto import ErrorDetail


def register_exception_handlers(
    app: FastAPI,
    logger: logging.Logger,
    settings: Settings,
) -> None:
    """Register global exception handlers."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle Pydantic validation errors and convert to custom ValidationError."""
        # Extract validation errors from Pydantic format
        errors = exc.errors()
        error_details = {}

        # Convert Pydantic errors to a more readable format
        for error in errors:
            loc = error.get("loc", [])
            field_path = str(loc[-1]) if loc else "unknown"
            error_type = error.get("type", "validation_error")
            error_msg = error.get("msg", "Validation failed")
            error_input = error.get("input")

            # Build field-specific error details
            if field_path not in error_details:
                error_details[field_path] = []

            error_details[field_path].append({
                "type": error_type,
                "message": error_msg,
                "input": error_input,
            })

        # Create ValidationError with details
        validation_error = ValidationError(
            message="Validation failed",
            details=error_details,
        )

        # Use ErrorResponse DTO for consistent format
        error_response = ErrorResponse(
            error=ErrorDetail(
                error_code=validation_error.error_code,
                message=validation_error.message,
                details=validation_error.details,
            )
        )

        return JSONResponse(
            status_code=validation_error.status_code,
            content=error_response.model_dump(),
        )

    @app.exception_handler(BitenexException)
    async def bitenex_exception_handler(
        request: Request,
        exc: BitenexException,
    ) -> JSONResponse:
        """Handle custom application exceptions."""
        # Use ErrorResponse DTO for consistent format
        error_response = ErrorResponse(
            error=ErrorDetail(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
            )
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception("Unexpected error occurred")

        # Don't expose internal errors in production
        message = str(exc) if settings.debug else "An unexpected error occurred"

        # Use ErrorResponse DTO for consistent format
        error_response = ErrorResponse(
            error=ErrorDetail(
                error_code="INTERNAL_ERROR",
                message=message,
                details={},
            )
        )

        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(),
        )
