from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gen_media_service.model.base_model import BaseModel


class LedgerEntry(BaseModel):
    __tablename__ = "ledger_entry"
    __table_args__ = (UniqueConstraint("kind", "external_ref", name="uq_ledger_kind_ref"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False)

    user = relationship("User", back_populates="ledger_entries")
