from sqlalchemy import (
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id")
    )

    kind: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    predicate: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True
    )

    value: Mapped[str | None] = mapped_column(
        Text
    )

    value_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    object_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id")
    )

    importance: Mapped[float] = mapped_column(
        Float,
        default=0.5
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5
    )

    status: Mapped[str] = mapped_column(
        String,
        default="current",
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


class MemoryVersion(Base):
    __tablename__ = "memory_versions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    memory_id: Mapped[int] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"),
        nullable=False
    )

    value: Mapped[str | None] = mapped_column(
        Text
    )

    value_type: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    object_entity_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id")
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    created_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    source_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False
    )


class MemoryLink(Base):
    __tablename__ = "memory_links"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    memory_id: Mapped[int] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"),
        nullable=False
    )

    start_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False
    )

    end_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id"),
        nullable=False
    )


class MemoryIndex(Base):
    __tablename__ = "memory_index"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    memory_id: Mapped[int] = mapped_column(
        ForeignKey("memory_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    search_terms: Mapped[str | None] = mapped_column(
        Text
    )

    updated_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )