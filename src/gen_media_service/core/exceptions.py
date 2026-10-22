class AppError(Exception):
    def __init__(self, message: str = "Internal application error") -> None:
        self.message = message
        super().__init__(message)


class AuthError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message)


class InsufficientTokensError(AppError):
    def __init__(self, message: str = "Insufficient tokens") -> None:
        super().__init__(message)


class TooManyActiveTasksError(AppError):
    def __init__(self, message: str = "Too many active tasks") -> None:
        super().__init__(message)
