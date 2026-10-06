from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from ...logger import debug_event
from ..models.entity_model import Entity
from ..models.relation_model import Relation
from ..utils import utc_now
from .base_repository import BaseRepository


class RelationRepository(BaseRepository):
    _RESOLUTIONS = {None, "update", "correction"}

    @classmethod
    def _normalize_resolution(cls, resolution):
        if resolution is None:
            return None

        if not isinstance(resolution, str):
            raise ValueError(
                f"Resolution inválida: {resolution}"
            )

        resolution = resolution.strip().lower()

        if resolution not in cls._RESOLUTIONS:
            raise ValueError(
                f"Resolution inválida: {resolution}"
            )

        return resolution

    def save(
        self,
        subject_entity_id,
        predicate,
        object_entity_id,
        symmetric,
        confidence,
        source_message_id,
        resolution=None
    ):
        if subject_entity_id is None:
            raise ValueError(
                "subject_entity_id não pode ser None"
            )

        if object_entity_id is None:
            raise ValueError(
                "object_entity_id não pode ser None"
            )

        if not predicate or not predicate.strip():
            raise ValueError(
                "predicate não pode ser vazio"
            )

        predicate = predicate.strip()
        symmetric = bool(symmetric)
        resolution = self._normalize_resolution(resolution)

        stmt = (
            select(Relation)
            .where(
                Relation.subject_entity_id == subject_entity_id,
                Relation.predicate == predicate,
                Relation.object_entity_id == object_entity_id
            )
            .limit(1)
        )

        with self.session() as session:
            existing = session.scalars(stmt).first()

            if not existing and symmetric:
                inverse_stmt = (
                    select(Relation)
                    .where(
                        Relation.subject_entity_id == object_entity_id,
                        Relation.predicate == predicate,
                        Relation.object_entity_id == subject_entity_id,
                        Relation.symmetric.is_(True)
                    )
                    .limit(1)
                )

                existing = session.scalars(inverse_stmt).first()

            if existing:
                if resolution in {"update", "correction"} and existing.status != "current":
                    current_stmt = (
                        select(Relation)
                        .where(
                            Relation.subject_entity_id == subject_entity_id,
                            Relation.predicate == predicate,
                            Relation.status == "current"
                        )
                    )

                    current_relations = session.scalars(
                        current_stmt
                    ).all()

                    for relation in current_relations:
                        relation.status = "historical"

                    existing.status = "current"

                    debug_event(
                        "RELATION_REACTIVATED",
                        relation_id=existing.id,
                        resolution=resolution,
                        subject_entity_id=subject_entity_id,
                        predicate=predicate,
                        object_entity_id=object_entity_id,
                        historical_relation_ids=[
                            relation.id
                            for relation in current_relations
                            if relation.id != existing.id
                        ]
                    )

                existing.symmetric = existing.symmetric or symmetric
                existing.confidence = max(
                    float(existing.confidence or 0),
                    float(confidence)
                )
                existing.source_message_id = source_message_id
                relation_id = existing.id
                inserted = False

            elif resolution in {"update", "correction"}:
                current_stmt = (
                    select(Relation)
                    .where(
                        Relation.subject_entity_id == subject_entity_id,
                        Relation.predicate == predicate,
                        Relation.status == "current",
                        Relation.object_entity_id != object_entity_id
                    )
                )

                current_relations = session.scalars(
                    current_stmt
                ).all()

                historical_relation_ids = []

                for relation in current_relations:
                    relation.status = "historical"
                    historical_relation_ids.append(relation.id)

                relation = Relation(
                    subject_entity_id=subject_entity_id,
                    predicate=predicate,
                    object_entity_id=object_entity_id,
                    symmetric=symmetric,
                    confidence=confidence,
                    status="current",
                    created_at=utc_now(),
                    source_message_id=source_message_id
                )

                session.add(relation)
                session.flush()

                relation_id = relation.id
                inserted = True

                debug_event(
                    "RELATION_UPDATE",
                    relation_id=relation_id,
                    resolution=resolution,
                    subject_entity_id=subject_entity_id,
                    predicate=predicate,
                    old_relation_ids=historical_relation_ids,
                    new_object_entity_id=object_entity_id
                )

            else:
                relation = Relation(
                    subject_entity_id=subject_entity_id,
                    predicate=predicate,
                    object_entity_id=object_entity_id,
                    symmetric=symmetric,
                    confidence=confidence,
                    status="current",
                    created_at=utc_now(),
                    source_message_id=source_message_id
                )

                session.add(relation)
                session.flush()

                relation_id = relation.id
                inserted = True

        debug_event(
            "RELATION_SAVE_COMPLETED",
            relation_id=relation_id,
            inserted=inserted,
            subject_entity_id=subject_entity_id,
            predicate=predicate,
            object_entity_id=object_entity_id,
            symmetric=symmetric,
            confidence=confidence,
            source_message_id=source_message_id,
            resolution=resolution
        )

        return relation_id

    def find_by_subject(
        self,
        subject_entity_id,
        predicate=None,
        limit=20
    ):
        ObjectEntity = aliased(Entity)

        stmt = (
            select(
                Relation.id,
                Entity.name.label("subject"),
                Relation.predicate,
                ObjectEntity.name.label("object"),
                Relation.subject_entity_id,
                Relation.object_entity_id,
                Relation.symmetric,
                Relation.confidence,
                Relation.status,
                Relation.created_at,
                Relation.source_message_id
            )
            .join(
                Entity,
                Entity.id == Relation.subject_entity_id
            )
            .join(
                ObjectEntity,
                ObjectEntity.id == Relation.object_entity_id
            )
            .where(
                Relation.subject_entity_id == subject_entity_id,
                Relation.status == "current"
            )
        )

        if predicate:
            stmt = stmt.where(
                Relation.predicate == predicate.strip()
            )

        stmt = (
            stmt
            .order_by(
                Relation.confidence.desc(),
                Relation.created_at.desc()
            )
            .limit(limit)
        )

        with self.session() as session:
            rows = session.execute(stmt).mappings().all()

        return [
            dict(row)
            for row in rows
        ]

    def find_by_object(
        self,
        object_entity_id,
        predicate=None,
        limit=20
    ):
        SubjectEntity = aliased(Entity)

        stmt = (
            select(
                Relation.id,
                SubjectEntity.name.label("subject"),
                Relation.predicate,
                Entity.name.label("object"),
                Relation.subject_entity_id,
                Relation.object_entity_id,
                Relation.symmetric,
                Relation.confidence,
                Relation.status,
                Relation.created_at,
                Relation.source_message_id
            )
            .join(
                SubjectEntity,
                SubjectEntity.id == Relation.subject_entity_id
            )
            .join(
                Entity,
                Entity.id == Relation.object_entity_id
            )
            .where(
                Relation.object_entity_id == object_entity_id,
                Relation.status == "current"
            )
        )

        if predicate:
            stmt = stmt.where(
                Relation.predicate == predicate.strip()
            )

        stmt = (
            stmt
            .order_by(
                Relation.confidence.desc(),
                Relation.created_at.desc()
            )
            .limit(limit)
        )

        with self.session() as session:
            rows = session.execute(stmt).mappings().all()

        return [
            dict(row)
            for row in rows
        ]

    def find_related(
        self,
        entity_id,
        predicate=None,
        direction="both",
        limit=20
    ):
        SubjectEntity = aliased(Entity)
        ObjectEntity = aliased(Entity)

        if direction == "subject":
            condition = or_(
                Relation.subject_entity_id == entity_id,
                and_(
                    Relation.object_entity_id == entity_id,
                    Relation.symmetric.is_(True)
                )
            )
        elif direction == "object":
            condition = or_(
                Relation.object_entity_id == entity_id,
                and_(
                    Relation.subject_entity_id == entity_id,
                    Relation.symmetric.is_(True)
                )
            )
        else:
            condition = or_(
                Relation.subject_entity_id == entity_id,
                Relation.object_entity_id == entity_id
            )

        stmt = (
            select(
                Relation.id,
                SubjectEntity.name.label("subject"),
                Relation.predicate,
                ObjectEntity.name.label("object"),
                Relation.subject_entity_id,
                Relation.object_entity_id,
                Relation.symmetric,
                Relation.confidence,
                Relation.status,
                Relation.created_at,
                Relation.source_message_id
            )
            .join(
                SubjectEntity,
                SubjectEntity.id == Relation.subject_entity_id
            )
            .join(
                ObjectEntity,
                ObjectEntity.id == Relation.object_entity_id
            )
            .where(
                condition,
                Relation.status == "current"
            )
        )

        if predicate:
            stmt = stmt.where(
                Relation.predicate == predicate.strip()
            )

        stmt = (
            stmt
            .order_by(
                Relation.confidence.desc(),
                Relation.created_at.desc()
            )
            .limit(limit)
        )

        with self.session() as session:
            rows = session.execute(stmt).mappings().all()

        result = [
            dict(row)
            for row in rows
        ]

        debug_event(
            "DB_RELATED_RELATIONS_RESULT",
            entity_id=entity_id,
            predicate=predicate,
            direction=direction,
            rows_count=len(result),
            rows=result
        )

        return result

    def find_between(
        self,
        subject_entity_id,
        object_entity_id,
        predicate=None
    ):
        conditions = [
            Relation.subject_entity_id == subject_entity_id,
            Relation.object_entity_id == object_entity_id,
            Relation.status == "current"
        ]

        if predicate:
            conditions.append(
                Relation.predicate == predicate.strip()
            )

        stmt = (
            select(Relation)
            .where(*conditions)
            .limit(1)
        )

        with self.session() as session:
            relation = session.scalars(stmt).first()

            if not relation:
                reverse_conditions = [
                    Relation.subject_entity_id == object_entity_id,
                    Relation.object_entity_id == subject_entity_id,
                    Relation.symmetric.is_(True),
                    Relation.status == "current"
                ]

                if predicate:
                    reverse_conditions.append(
                        Relation.predicate == predicate.strip()
                    )

                reverse_stmt = (
                    select(Relation)
                    .where(*reverse_conditions)
                    .limit(1)
                )

                relation = session.scalars(
                    reverse_stmt
                ).first()

        if not relation:
            return None

        return {
            "id": relation.id,
            "subject_entity_id": relation.subject_entity_id,
            "predicate": relation.predicate,
            "object_entity_id": relation.object_entity_id,
            "symmetric": relation.symmetric,
            "confidence": relation.confidence,
            "status": relation.status,
            "created_at": relation.created_at,
            "source_message_id": relation.source_message_id
        }

    def count_related(
        self,
        entity_id,
        predicate=None,
        direction="both"
    ):
        if direction == "subject":
            condition = or_(
                Relation.subject_entity_id == entity_id,
                and_(
                    Relation.object_entity_id == entity_id,
                    Relation.symmetric.is_(True)
                )
            )
        elif direction == "object":
            condition = or_(
                Relation.object_entity_id == entity_id,
                and_(
                    Relation.subject_entity_id == entity_id,
                    Relation.symmetric.is_(True)
                )
            )
        else:
            condition = or_(
                Relation.subject_entity_id == entity_id,
                Relation.object_entity_id == entity_id
            )

        stmt = (
            select(
                func.count(
                    func.distinct(Relation.id)
                )
            )
            .where(
                condition,
                Relation.status == "current"
            )
        )

        if predicate:
            stmt = stmt.where(
                Relation.predicate == predicate.strip()
            )

        with self.session() as session:
            return int(session.scalar(stmt) or 0)

    def count_by_subject(
        self,
        subject_entity_id,
        predicate=None
    ):
        return self.count_related(
            entity_id=subject_entity_id,
            predicate=predicate,
            direction="subject"
        )

    def count_by_object(
        self,
        object_entity_id,
        predicate=None
    ):
        return self.count_related(
            entity_id=object_entity_id,
            predicate=predicate,
            direction="object"
        )