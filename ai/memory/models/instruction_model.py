from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Instruction(Base):
    __tablename__ = "instructions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String,
        default="active",
        nullable=False
    )

    created_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    updated_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    source_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False
    )