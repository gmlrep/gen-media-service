from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from gen_media_service.adapters.provider import ProviderClient, ProviderError
from gen_media_service.core.config import Settings
from gen_media_service.core.exceptions import (
    InsufficientTokensError,
    NotFoundError,
    TooManyActiveTasksError,
    ValidationError,
)
from gen_media_service.model.catalog import ModelLeg
from gen_media_service.model.task import GenerationTask, TaskAttempt
from gen_media_service.repository.catalog import CatalogRepository
from gen_media_service.repository.ledger import LedgerRepository
from gen_media_service.repository.task import TaskRepository
from gen_media_service.repository.user import UserRepository
from gen_media_service.schema.generate import (
    AttemptHistoryItem,
    GenerateRequest,
    GenerateResponse,
    TaskRead,
)
from gen_media_service.schema.provider_webhook import ProviderWebhook
from gen_media_service.services.base import BaseService


class GenerationService(BaseService):
    def __init__(
        self,
        task_repository: TaskRepository,
        catalog_repository: CatalogRepository,
        ledger_repository: LedgerRepository,
        user_repository: UserRepository,
        provider_client: ProviderClient,
        settings: Settings,
    ) -> None:
        self.task_repository = task_repository
        self.catalog_repository = catalog_repository
        self.ledger_repository = ledger_repository
        self.user_repository = user_repository
        self.provider_client = provider_client
        self.settings = settings
        super().__init__(task_repository)

    async def generate(self, payload: GenerateRequest) -> GenerateResponse:
        async with self.task_repository.session_factory() as session:
            model = await self.catalog_repository.get_by_slug(session, payload.model_slug)
            if model is None:
                raise ValidationError(f"Unknown model: {payload.model_slug}")

            legs = [
                leg for leg in model.legs if leg.max_ref_images >= len(payload.ref_images)
            ]
            if not legs:
                raise ValidationError("No provider leg accepts the given number of ref_images")

            await self.user_repository.get_or_create(session, payload.user_id)
            active = await self.task_repository.count_active(session, payload.user_id)
            if active >= self.settings.MAX_ACTIVE_TASKS:
                raise TooManyActiveTasksError(
                    f"User already has {active} active tasks (max {self.settings.MAX_ACTIVE_TASKS})"
                )

            user = await self.user_repository.get_for_update(session, payload.user_id)
            assert user is not None
            if user.balance < model.price_tokens:
                raise InsufficientTokensError("Insufficient tokens")

            task = await self.task_repository.create_task(
                session,
                user_id=payload.user_id,
                model_slug=payload.model_slug,
                prompt=payload.prompt,
                ref_images=payload.ref_images,
                price_tokens=model.price_tokens,
            )

            charged = await self.ledger_repository.try_apply(
                session,
                user_id=payload.user_id,
                amount=-model.price_tokens,
                kind="charge",
                external_ref=str(task.id),
            )
            if not charged:
                raise ValidationError("Task charge already applied")

            task.status = "running"
            await session.flush()

            # Persist task id before calling providers so retries see charged task
            task_id = task.id
            await self._try_legs(
                session,
                task=task,
                legs=legs,
                start_index=0,
                after_moderation=False,
            )
            return GenerateResponse(task_id=task_id)

    async def get_task(self, task_id: int) -> TaskRead:
        async with self.task_repository.session_factory() as session:
            task = await self.task_repository.get_with_attempts(session, task_id)
            if task is None:
                raise NotFoundError(f"Task {task_id} not found")
            return self._to_task_read(task)

    async def handle_provider_webhook(
        self, provider_name: str, payload: ProviderWebhook
    ) -> None:
        async with self.task_repository.session_factory() as session:
            found = await self.task_repository.get_by_external_id_for_update(
                session, payload.external_id
            )
            if found is None:
                return

            task, attempt = found
            if attempt.provider != provider_name:
                return

            # Late / duplicate: only waiting attempts accept outcomes
            if attempt.status != "waiting":
                return

            if payload.status == "completed":
                await self._complete_attempt(session, task, attempt, payload.result_url)
                return

            if payload.status == "failed":
                error_type = payload.error_type or "technical"
                await self._fail_attempt_and_advance(session, task, attempt, error_type)
                return

    async def process_timeouts(self) -> int:
        async with self.task_repository.session_factory() as session:
            claimed = await self.task_repository.claim_timed_out_attempts(session)
            processed = 0
            for attempt in claimed:
                task = await self.task_repository.get_for_update(session, attempt.task_id)
                if task is None:
                    continue
                if task.status not in ("pending", "running"):
                    continue
                # Re-load attempt after claim (status already timeout)
                for a in task.attempts:
                    if a.id == attempt.id:
                        await self._advance_after_failure(
                            session, task, a, error_type="technical"
                        )
                        processed += 1
                        break
            return processed

    async def _try_legs(
        self,
        session: AsyncSession,
        *,
        task: GenerationTask,
        legs: list[ModelLeg],
        start_index: int,
        after_moderation: bool,
    ) -> None:
        index = start_index
        while index < len(legs):
            leg = legs[index]
            if after_moderation and leg.skip_on_moderation:
                index += 1
                continue

            attempt = await self.task_repository.create_attempt(
                session,
                task_id=task.id,
                provider=leg.provider,
                leg_priority=leg.priority,
            )
            task.current_attempt_id = attempt.id
            task.status = "running"
            await session.flush()

            try:
                result = await self.provider_client.submit_task(
                    provider=leg.provider,
                    prompt=task.prompt,
                    ref_images=list(task.ref_images or []),
                    model_slug=task.model_slug,
                )
            except ProviderError:
                now = datetime.now(timezone.utc)
                attempt.status = "failed"
                attempt.error_type = "technical"
                attempt.finished_at = now
                await session.flush()
                index += 1
                after_moderation = False
                continue

            timeout_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.settings.providers.PROVIDER_TIMEOUT
            )
            await self.task_repository.mark_attempt_waiting(
                session, attempt, result.external_id, timeout_at
            )
            return

        await self._fail_task_and_refund(session, task)

    async def _complete_attempt(
        self,
        session: AsyncSession,
        task: GenerationTask,
        attempt: TaskAttempt,
        result_url: str | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        attempt.status = "succeeded"
        attempt.finished_at = now
        task.status = "completed"
        task.result_url = result_url
        await session.flush()

    async def _fail_attempt_and_advance(
        self,
        session: AsyncSession,
        task: GenerationTask,
        attempt: TaskAttempt,
        error_type: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        attempt.status = "failed"
        attempt.error_type = error_type
        attempt.finished_at = now
        await session.flush()
        await self._advance_after_failure(session, task, attempt, error_type)

    async def _advance_after_failure(
        self,
        session: AsyncSession,
        task: GenerationTask,
        failed_attempt: TaskAttempt,
        error_type: str,
    ) -> None:
        if task.status in ("completed", "failed"):
            return

        if error_type == "payload":
            await self._fail_task_and_refund(session, task)
            return

        model = await self.catalog_repository.get_by_slug(session, task.model_slug)
        if model is None:
            await self._fail_task_and_refund(session, task)
            return

        legs = [
            leg for leg in model.legs if leg.max_ref_images >= len(task.ref_images or [])
        ]
        failed_idx = None
        for i, leg in enumerate(legs):
            if (
                leg.priority == failed_attempt.leg_priority
                and leg.provider == failed_attempt.provider
            ):
                failed_idx = i
                break
        start = (failed_idx + 1) if failed_idx is not None else len(legs)
        after_moderation = error_type == "moderation"
        await self._try_legs(
            session,
            task=task,
            legs=legs,
            start_index=start,
            after_moderation=after_moderation,
        )

    async def _fail_task_and_refund(
        self, session: AsyncSession, task: GenerationTask
    ) -> None:
        if task.status == "failed":
            return
        task.status = "failed"
        await session.flush()
        await self.ledger_repository.try_apply(
            session,
            user_id=task.user_id,
            amount=task.price_tokens,
            kind="refund",
            external_ref=str(task.id),
        )

    def _to_task_read(self, task: GenerationTask) -> TaskRead:
        current_provider = None
        if task.current_attempt_id:
            for a in task.attempts:
                if a.id == task.current_attempt_id:
                    current_provider = a.provider
                    break
        return TaskRead(
            id=task.id,
            status=task.status,
            model_slug=task.model_slug,
            current_provider=current_provider,
            result_url=task.result_url,
            attempts=[
                AttemptHistoryItem(
                    provider=a.provider,
                    status=a.status,
                    error_type=a.error_type,
                    started_at=a.started_at,
                    finished_at=a.finished_at,
                )
                for a in task.attempts
            ],
        )
