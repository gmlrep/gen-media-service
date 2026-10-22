from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gen_media_service.model.base_model import BaseModel


class GenerationModel(BaseModel):
    __tablename__ = "generation_model"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    price_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    legs = relationship(
        "ModelLeg",
        back_populates="model",
        order_by="ModelLeg.priority",
        cascade="all, delete-orphan",
    )


class ModelLeg(BaseModel):
    __tablename__ = "model_leg"

    model_id: Mapped[int] = mapped_column(ForeignKey("generation_model.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    max_ref_images: Mapped[int] = mapped_column(Integer, nullable=False)
    skip_on_moderation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    model = relationship("GenerationModel", back_populates="legs")
