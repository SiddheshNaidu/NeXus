from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    SEARCH_ERROR = "SEARCH_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class NexusError(Exception):
    """Base application error. Maps to a structured JSON response."""

    def __init__(self, code: ErrorCode, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(NexusError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(ErrorCode.NOT_FOUND, message, 404)


class ForbiddenError(NexusError):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(ErrorCode.FORBIDDEN, message, 403)


class UnauthorizedError(NexusError):
    def __init__(self, message: str = "Authentication is required."):
        super().__init__(ErrorCode.UNAUTHORIZED, message, 401)


class ConflictError(NexusError):
    def __init__(self, message: str = "A conflict occurred."):
        super().__init__(ErrorCode.CONFLICT, message, 409)


class ValidationError(NexusError):
    def __init__(self, message: str = "Validation failed."):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, 422)


class InternalError(NexusError):
    def __init__(self, message: str = "An internal error occurred."):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, 500)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def nexus_error_handler(request: Request, exc: NexusError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code.value, exc.message),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all — never expose stack traces."""
    return JSONResponse(
        status_code=500,
        content=_error_body(ErrorCode.INTERNAL_ERROR.value, "An unexpected error occurred."),
    )
