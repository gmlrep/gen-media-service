from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gen_media_service.core.exceptions import (
    AppError,
    AuthError,
    InsufficientTokensError,
    NotFoundError,
    TooManyActiveTasksError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def auth_error_handler(_: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(InsufficientTokensError)
    async def insufficient_tokens_handler(_: Request, exc: InsufficientTokensError) -> JSONResponse:
        return JSONResponse(status_code=402, content={"detail": exc.message})

    @app.exception_handler(TooManyActiveTasksError)
    async def too_many_tasks_handler(_: Request, exc: TooManyActiveTasksError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": exc.message})

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": exc.message})
