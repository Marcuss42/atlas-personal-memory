from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    entity_type: Mapped[str | None] = mapped_column(
        String
    )

    created_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )

    updated_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False
    )


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id"),
        nullable=False,
        index=True
    )

    alias: Mapped[str] = mapped_column(
        String,
        nullable=False
    )