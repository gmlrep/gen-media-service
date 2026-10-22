import asyncio
import logging

from gen_media_service.services.generation import GenerationService

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(
        self,
        generation_service: GenerationService,
        interval_seconds: float = 1.0,
    ) -> None:
        self._service = generation_service
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        self._stopped.clear()
        self._task = asyncio.create_task(self._run(), name="provider-watchdog")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                processed = await self._service.process_timeouts()
                if processed:
                    logger.info("Watchdog processed %s timed-out attempts", processed)
            except Exception:
                logger.exception("Watchdog iteration failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._interval)
            except TimeoutError:
                continue
