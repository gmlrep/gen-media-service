from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gen_media_service.model.base_model import BaseModel


class GenerationTask(BaseModel):
    __tablename__ = "generation_task"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    model_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    ref_images: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    price_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    user = relationship("User", back_populates="tasks")
    attempts = relationship(
        "TaskAttempt",
        back_populates="task",
        order_by="TaskAttempt.id",
        cascade="all, delete-orphan",
    )


class TaskAttempt(BaseModel):
    __tablename__ = "task_attempt"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("generation_task.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sending")
    error_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leg_priority: Mapped[int] = mapped_column(Integer, nullable=False)

    task = relationship("GenerationTask", back_populates="attempts")
