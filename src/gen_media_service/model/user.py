from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gen_media_service.model.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    ledger_entries = relationship("LedgerEntry", back_populates="user")
    tasks = relationship("GenerationTask", back_populates="user")
