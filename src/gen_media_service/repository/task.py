from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gen_media_service.model.task import GenerationTask, TaskAttempt
from gen_media_service.repository.base import BaseRepository

ACTIVE_STATUSES = ("pending", "running")


class TaskRepository(BaseRepository[GenerationTask]):
    model = GenerationTask

    async def count_active(self, session: AsyncSession, user_id: int) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(GenerationTask)
            .where(
                GenerationTask.user_id == user_id,
                GenerationTask.status.in_(ACTIVE_STATUSES),
            )
        )
        return int(result.scalar_one())

    async def create_task(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        model_slug: str,
        prompt: str,
        ref_images: list[str],
        price_tokens: int,
    ) -> GenerationTask:
        task = GenerationTask(
            user_id=user_id,
            model_slug=model_slug,
            prompt=prompt,
            ref_images=ref_images,
            status="pending",
            price_tokens=price_tokens,
        )
        session.add(task)
        await session.flush()
        return task

    async def get_with_attempts(
        self, session: AsyncSession, task_id: int
    ) -> GenerationTask | None:
        result = await session.execute(
            select(GenerationTask)
            .where(GenerationTask.id == task_id)
            .options(selectinload(GenerationTask.attempts))
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, session: AsyncSession, task_id: int) -> GenerationTask | None:
        result = await session.execute(
            select(GenerationTask)
            .where(GenerationTask.id == task_id)
            .options(selectinload(GenerationTask.attempts))
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_external_id_for_update(
        self, session: AsyncSession, external_id: str
    ) -> tuple[GenerationTask, TaskAttempt] | None:
        result = await session.execute(
            select(TaskAttempt)
            .where(TaskAttempt.external_id == external_id)
            .order_by(TaskAttempt.id.desc())
            .limit(1)
            .with_for_update()
        )
        attempt = result.scalar_one_or_none()
        if attempt is None:
            return None
        task_result = await session.execute(
            select(GenerationTask)
            .where(GenerationTask.id == attempt.task_id)
            .options(selectinload(GenerationTask.attempts))
            .with_for_update()
        )
        task = task_result.scalar_one()
        return task, attempt

    async def create_attempt(
        self,
        session: AsyncSession,
        *,
        task_id: int,
        provider: str,
        leg_priority: int,
        timeout_at: datetime | None = None,
    ) -> TaskAttempt:
        now = datetime.now(timezone.utc)
        attempt = TaskAttempt(
            task_id=task_id,
            provider=provider,
            status="sending",
            started_at=now,
            timeout_at=timeout_at,
            leg_priority=leg_priority,
        )
        session.add(attempt)
        await session.flush()
        return attempt

    async def mark_attempt_waiting(
        self,
        session: AsyncSession,
        attempt: TaskAttempt,
        external_id: str,
        timeout_at: datetime,
    ) -> None:
        attempt.external_id = external_id
        attempt.status = "waiting"
        attempt.timeout_at = timeout_at
        await session.flush()

    async def claim_timed_out_attempts(
        self, session: AsyncSession, limit: int = 20
    ) -> list[TaskAttempt]:
        now = datetime.now(timezone.utc)
        # Claim waiting attempts past timeout using SKIP LOCKED (safe with 4 workers).
        result = await session.execute(
            select(TaskAttempt)
            .where(
                TaskAttempt.status == "waiting",
                TaskAttempt.timeout_at.is_not(None),
                TaskAttempt.timeout_at < now,
            )
            .order_by(TaskAttempt.timeout_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        attempts = list(result.scalars().all())
        for attempt in attempts:
            attempt.status = "timeout"
            attempt.error_type = "technical"
            attempt.finished_at = now
        if attempts:
            await session.flush()
        return attempts
