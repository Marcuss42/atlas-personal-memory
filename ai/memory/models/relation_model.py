from sqlalchemy import Boolean, ForeignKey, Integer, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    subject_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id"),
        nullable=False
    )

    predicate: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    object_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id"),
        nullable=False
    )

    symmetric: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5
    )

    status: Mapped[str] = mapped_column(
        String,
        default="current",
        nullable=False,
        index=True
    )

    created_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    source_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "subject_entity_id",
            "predicate",
            "object_entity_id"
        ),
    )