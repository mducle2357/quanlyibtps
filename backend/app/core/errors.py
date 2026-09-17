class AppError(Exception):
    """Base for errors that should render as a structured JSON body (prompt §30:
    'Endpoint phải trả lỗi có cấu trúc'), not a bare 500/HTML page."""

    status_code = 400
    error_code = "app_error"

    def __init__(self, message: str, *, error_code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code


class ConflictError(AppError):
    """Raised when a save is based on a stale version (prompt §3)."""

    status_code = 409
    error_code = "conflict"

    def __init__(self, current_version: int, message: str | None = None):
        super().__init__(
            message
            or "Dữ liệu đã được thay đổi bởi người dùng khác. Vui lòng tải lại hoặc xem thay đổi trước khi ghi đè.",
            error_code="conflict",
        )
        self.current_version = current_version


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    error_code = "validation_error"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "forbidden"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "unauthorized"
