from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gen_media_service.infrastructure.watchdog import Watchdog


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = app.state.container
    watchdog: Watchdog = Watchdog(
        generation_service=container.generation_service(),
        interval_seconds=container.settings().WATCHDOG_INTERVAL_SECONDS,
    )
    app.state.watchdog = watchdog
    await watchdog.start()
    try:
        yield
    finally:
        await watchdog.stop()
        await container.db().dispose()
