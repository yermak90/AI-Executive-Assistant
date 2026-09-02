class AppError(Exception):
    """Base class for application-level errors mapped to HTTP responses."""

    status_code: int = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class ValidationAppError(AppError):
    status_code = 422


class ConflictError(AppError):
    """Invalid state transition or a conflicting operation (HTTP 409)."""

    status_code = 409
