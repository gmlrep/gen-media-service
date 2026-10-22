import uvicorn
from fastapi import FastAPI

from gen_media_service.api.routes import api_router
from gen_media_service.core.config import settings
from gen_media_service.core.container import Container
from gen_media_service.core.exception_handlers import register_exception_handlers
from gen_media_service.core.lifespan import lifespan


class AppCreator:
    def __init__(self) -> None:
        settings.validate_for_api()
        self.container = Container()
        self.app = FastAPI(
            title=settings.APP_NAME,
            lifespan=lifespan,
        )
        self.app.state.container = self.container
        register_exception_handlers(self.app)
        self.app.include_router(api_router)


def create_app() -> FastAPI:
    return AppCreator().app


app = create_app()


def main() -> None:
    uvicorn.run(
        "gen_media_service.__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
