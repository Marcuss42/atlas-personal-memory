from sqlalchemy import func, select

from ...logger import debug_event
from ..models.entity_model import Entity, EntityAlias
from ..utils import normalize, utc_now
from .base_repository import BaseRepository


class EntityRepository(BaseRepository):
    def ensure_user_entity(
        self,
        name="Usuário",
        entity_type="person"
    ):
        entity_id = self.resolve(
            name,
            entity_type
        )

        debug_event(
            "DB_USER_ENTITY",
            entity_id=entity_id,
            name=name
        )

        return entity_id

    def resolve(
        self,
        name,
        entity_type=None
    ):
        if not name or not str(name).strip():
            raise ValueError(
                "Nome da entidade não pode ser vazio"
            )

        normalized = normalize(
            str(name).strip()
        )

        name_stmt = (
            select(Entity)
            .where(
                func.lower(Entity.name) == normalized
            )
            .limit(1)
        )

        debug_event(
            "DB_ENTITY_LOOKUP",
            name=name,
            normalized=normalized,
            sql=str(name_stmt)
        )

        with self.session() as session:
            entity = session.scalars(
                name_stmt
            ).first()

            if entity:
                return entity.id

            alias_stmt = (
                select(EntityAlias)
                .where(
                    func.lower(EntityAlias.alias) == normalized
                )
                .limit(1)
            )

            debug_event(
                "DB_ALIAS_LOOKUP",
                name=name,
                normalized=normalized,
                sql=str(alias_stmt)
            )

            alias = session.scalars(
                alias_stmt
            ).first()

            if alias:
                return alias.entity_id

            now = utc_now()

            entity = Entity(
                name=str(name).strip(),
                entity_type=entity_type,
                created_at=now,
                updated_at=now
            )

            session.add(entity)
            session.flush()

            entity_id = entity.id

        debug_event(
            "ENTITY_CREATED",
            name=name,
            entity_id=entity_id,
            entity_type=entity_type
        )

        return entity_id

    def find_by_name_or_alias(
        self,
        name
    ):
        if not name or not str(name).strip():
            return None

        normalized = normalize(
            str(name).strip()
        )

        name_stmt = (
            select(Entity.id)
            .where(
                func.lower(Entity.name) == normalized
            )
            .limit(1)
        )

        debug_event(
            "DB_ENTITY_FIND",
            name=name,
            normalized=normalized,
            sql=str(name_stmt)
        )

        with self.session() as session:
            entity_id = session.scalar(
                name_stmt
            )

            if entity_id is not None:
                return entity_id

            alias_stmt = (
                select(EntityAlias.entity_id)
                .where(
                    func.lower(EntityAlias.alias) == normalized
                )
                .limit(1)
            )

            debug_event(
                "DB_ALIAS_FIND",
                name=name,
                normalized=normalized,
                sql=str(alias_stmt)
            )

            entity_id = session.scalar(
                alias_stmt
            )

            if entity_id is not None:
                return entity_id

            return self._find_flexible(
                session,
                normalized
            )

    @staticmethod
    def _lookup_normalized(value):
        value = str(value or "").strip().lower()

        value = "".join(
            " "
            if char in "-_"
            else char
            for char in value
        )

        return " ".join(
            value.split()
        )

    @classmethod
    def _find_flexible(
        cls,
        session,
        normalized
    ):
        lookup = cls._lookup_normalized(
            normalized
        )

        if not lookup:
            return None

        entities = session.scalars(
            select(Entity)
        ).all()

        for entity in entities:
            entity_lookup = cls._lookup_normalized(
                entity.name
            )

            if entity_lookup == lookup:
                debug_event(
                    "DB_ENTITY_FIND_FLEXIBLE",
                    normalized=normalized,
                    matched_name=entity.name,
                    entity_id=entity.id
                )

                return entity.id

        aliases = session.execute(
            select(
                EntityAlias.entity_id,
                EntityAlias.alias
            )
        ).all()

        for entity_id, alias in aliases:
            alias_lookup = cls._lookup_normalized(
                alias
            )

            if alias_lookup == lookup:
                debug_event(
                    "DB_ALIAS_FIND_FLEXIBLE",
                    normalized=normalized,
                    matched_alias=alias,
                    entity_id=entity_id
                )

                return entity_id

        return None

    def add_alias(
        self,
        entity_id,
        alias
    ):
        if not alias or not str(alias).strip():
            raise ValueError(
                "Alias não pode ser vazio"
            )

        alias = str(alias).strip()
        normalized = normalize(alias)

        with self.session() as session:
            exists = session.scalar(
                select(EntityAlias.id)
                .where(
                    EntityAlias.entity_id == entity_id,
                    func.lower(EntityAlias.alias) == normalized
                )
                .limit(1)
            )

            if exists:
                return

            session.add(
                EntityAlias(
                    entity_id=entity_id,
                    alias=alias
                )
            )

        debug_event(
            "DB_ALIAS_SAVED",
            entity_id=entity_id,
            alias=alias
        )