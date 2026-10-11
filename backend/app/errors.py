from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class InsufficientDataError(AppError):
    status_code = 422
    code = "insufficient_data"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


class UpstreamTimeout(AppError):
    status_code = 504
    code = "upstream_timeout"


class DatabaseUnavailable(AppError):
    status_code = 503
    code = "database_unavailable"
