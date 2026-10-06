import json
import re

from sqlalchemy import (
    distinct,
    func,
    or_,
    select,
    text
)

from ...logger import debug_event
from ..models.entity_model import Entity, EntityAlias
from ..models.memory_model import (
    MemoryIndex,
    MemoryItem,
    MemoryLink,
    MemoryVersion
)
from ..utils import normalize, utc_now
from .base_repository import BaseRepository


class MemoryRepository(BaseRepository):
    _SEARCH_STOPWORDS = {
        "a",
        "as",
        "ao",
        "aos",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "eu",
        "é",
        "ha",
        "há",
        "me",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "para",
        "por",
        "que",
        "se",
        "tem",
        "tenho",
        "qual",
        "quais",
        "quem",
        "quantos",
        "quantas",
        "uma",
        "umas",
        "um",
        "uns",
        "como",
        "onde",
        "quando"
    }

    def save(
        self,
        subject_entity_id,
        kind,
        predicate,
        value,
        value_type,
        object_entity_id,
        importance,
        confidence,
        source_message_id,
        search_terms=None,
        resolution=None
    ):
        lookup_stmt = (
            select(MemoryItem)
            .where(
                MemoryItem.entity_id == subject_entity_id,
                MemoryItem.predicate == predicate,
                MemoryItem.object_entity_id == object_entity_id,
                MemoryItem.status == "current"
            )
            .order_by(
                MemoryItem.updated_at.desc(),
                MemoryItem.id.desc()
            )
        )

        debug_event(
            "MEMORY_SAVE_START",
            subject_entity_id=subject_entity_id,
            predicate=predicate,
            value=value,
            value_type=value_type,
            object_entity_id=object_entity_id,
            search_terms=search_terms,
            resolution=resolution,
            sql=str(lookup_stmt)
        )

        with self.session() as session:
            existing_items = session.scalars(
                lookup_stmt
            ).all()

            existing = None

            for item in existing_items:
                if (
                    item.value == value
                    and item.value_type == value_type
                ):
                    existing = item
                    break

            if existing:
                memory_id = existing.id

                debug_event(
                    "MEMORY_UNCHANGED",
                    memory_id=memory_id,
                    predicate=predicate,
                    value=value,
                    object_entity_id=object_entity_id
                )

                status = existing.status

            elif (
                resolution in {"update", "correction"}
                and len(existing_items) == 1
            ):
                existing = existing_items[0]
                memory_id = existing.id
                now = utc_now()

                old_value = existing.value
                old_value_type = existing.value_type
                old_object_entity_id = existing.object_entity_id

                current_version_stmt = (
                    select(MemoryVersion)
                    .where(
                        MemoryVersion.memory_id == memory_id,
                        MemoryVersion.status == "current"
                    )
                )

                current_version = session.scalars(
                    current_version_stmt
                ).first()

                if current_version:
                    current_version.status = "historical"

                session.add(
                    MemoryVersion(
                        memory_id=memory_id,
                        value=value,
                        value_type=value_type,
                        object_entity_id=object_entity_id,
                        status="current",
                        created_at=now,
                        source_message_id=source_message_id
                    )
                )

                existing.value = value
                existing.value_type = value_type
                existing.object_entity_id = object_entity_id
                existing.importance = importance
                existing.confidence = confidence
                existing.updated_at = now

                status = existing.status

                debug_event(
                    "MEMORY_UPDATE",
                    memory_id=memory_id,
                    resolution=resolution,
                    old_value=old_value,
                    new_value=value,
                    old_value_type=old_value_type,
                    new_value_type=value_type,
                    old_object_entity_id=old_object_entity_id,
                    new_object_entity_id=object_entity_id
                )

            else:
                now = utc_now()

                item = MemoryItem(
                    entity_id=subject_entity_id,
                    kind=kind,
                    predicate=predicate,
                    value=value,
                    value_type=value_type,
                    object_entity_id=object_entity_id,
                    importance=importance,
                    confidence=confidence,
                    status="current",
                    created_at=now,
                    updated_at=now
                )

                session.add(item)
                session.flush()

                session.add(
                    MemoryVersion(
                        memory_id=item.id,
                        value=value,
                        value_type=value_type,
                        object_entity_id=object_entity_id,
                        status="current",
                        created_at=now,
                        source_message_id=source_message_id
                    )
                )

                memory_id = item.id
                status = item.status

                if existing_items:
                    debug_event(
                        "MEMORY_CONFLICT",
                        memory_id=memory_id,
                        conflicting_memory_ids=[
                            item.id
                            for item in existing_items
                        ],
                        predicate=predicate,
                        value=value,
                        value_type=value_type,
                        object_entity_id=object_entity_id
                    )
                else:
                    debug_event(
                        "MEMORY_CREATE",
                        memory_id=memory_id
                    )

            session.add(
                MemoryLink(
                    memory_id=memory_id,
                    start_message_id=source_message_id,
                    end_message_id=source_message_id
                )
            )

        try:
            self.save_index(
                memory_id,
                search_terms
            )
        except Exception as exc:
            debug_event(
                "MEMORY_INDEX_ERROR",
                memory_id=memory_id,
                predicate=predicate,
                error=repr(exc)
            )

        debug_event(
            "MEMORY_SAVE_COMPLETED",
            memory_id=memory_id,
            predicate=predicate,
            value=value,
            object_entity_id=object_entity_id,
            status=status,
            resolution=resolution
        )

        return memory_id

    def get(self, memory_id):
        stmt = (
            select(
                MemoryItem,
                Entity.name,
                MemoryIndex.search_terms
            )
            .outerjoin(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .outerjoin(
                MemoryIndex,
                MemoryIndex.memory_id == MemoryItem.id
            )
            .where(
                MemoryItem.id == memory_id
            )
            .limit(1)
        )

        debug_event(
            "DB_GET_MEMORY",
            memory_id=memory_id,
            sql=str(stmt)
        )

        with self.session() as session:
            row = session.execute(
                stmt
            ).first()

        if not row:
            return None

        item, entity_name, search_terms = row

        if search_terms:
            try:
                search_terms = json.loads(search_terms)
            except json.JSONDecodeError:
                search_terms = []

        return {
            "id": item.id,
            "entity_id": item.entity_id,
            "entity": entity_name,
            "kind": item.kind,
            "predicate": item.predicate,
            "value": item.value,
            "value_type": item.value_type,
            "object_entity_id": item.object_entity_id,
            "importance": item.importance,
            "confidence": item.confidence,
            "status": item.status,
            "search_terms": search_terms or []
        }

    def save_index(self, memory_id, search_terms=None):
        item = self.get(memory_id)

        if not item:
            raise ValueError(
                f"Memória não encontrada: {memory_id}"
            )

        if search_terms is None:
            search_terms = item.get(
                "search_terms",
                []
            )

        search_terms = self._normalize_index_terms(
            search_terms
        )

        with self.session() as session:
            aliases_stmt = (
                select(EntityAlias.alias)
                .where(
                    EntityAlias.entity_id == item["entity_id"]
                )
            )

            aliases = session.scalars(
                aliases_stmt
            ).all()

            fields = [
                item["entity"],
                item["predicate"],
                item["value"],
                *aliases,
                *search_terms
            ]

            search_text = " ".join(
                str(field)
                for field in fields
                if field
            )

            stmt = (
                select(MemoryIndex)
                .where(
                    MemoryIndex.memory_id == memory_id
                )
                .limit(1)
            )

            index = session.scalars(
                stmt
            ).first()

            if not index:
                index = MemoryIndex(
                    memory_id=memory_id,
                    search_text=search_text,
                    search_terms=json.dumps(
                        search_terms,
                        ensure_ascii=False
                    ),
                    updated_at=utc_now()
                )

                session.add(index)

            else:
                index.search_text = search_text
                index.search_terms = json.dumps(
                    search_terms,
                    ensure_ascii=False
                )
                index.updated_at = utc_now()

        debug_event(
            "DB_MEMORY_INDEX_SAVED",
            memory_id=memory_id,
            search_terms=search_terms,
            search_text=search_text
        )

    @classmethod
    def _extract_search_terms(cls, query, minimum_length=2):
        terms = re.findall(
            r"\w+",
            normalize(query),
            flags=re.UNICODE
        )

        result = []

        for term in terms:
            if len(term) < minimum_length:
                continue

            if term in cls._SEARCH_STOPWORDS:
                continue

            if term not in result:
                result.append(term)

        return result

    @staticmethod
    def _normalize_index_terms(terms):
        if not terms:
            return []

        result = []

        for term in terms:
            if not isinstance(term, str):
                continue

            term = normalize(term)

            if term and term not in result:
                result.append(term)

        return result

    @staticmethod
    def _score_search_text(search_text, terms, normalized_query=None):
        normalized_text = normalize(search_text or "")

        if not normalized_text or not terms:
            return 0

        score = 0

        tokens = set(
            re.findall(
                r"\w+",
                normalized_text,
                flags=re.UNICODE
            )
        )

        for term in terms:
            if term in tokens:
                score += 1

        if normalized_query:
            phrase = normalize(normalized_query)

            if phrase and phrase in normalized_text:
                score += 3

        return score

    def update_index(self, memory_id, search_terms):
        debug_event(
            "MEMORY_INDEX_UPDATE",
            memory_id=memory_id,
            search_terms=search_terms
        )

        self.save_index(
            memory_id,
            search_terms
        )

    def refresh_entity_indexes(self, entity_id):
        stmt = (
            select(MemoryItem.id)
            .where(
                MemoryItem.entity_id == entity_id,
                MemoryItem.status == "current"
            )
        )

        with self.session() as session:
            memory_ids = session.scalars(
                stmt
            ).all()

        for memory_id in memory_ids:
            self.save_index(memory_id)

    def search_index(self, query, limit=10):
        terms = self._extract_search_terms(
            query,
            minimum_length=2
        )

        if not terms:
            return []

        fts_query = " OR ".join(
            f'"{term}"'
            for term in terms
        )

        candidate_limit = max(
            limit * 5,
            20
        )

        sql = text("""
            SELECT DISTINCT
                m.id,
                e.name AS entity,
                m.kind,
                m.predicate,
                m.value,
                m.value_type,
                m.object_entity_id,
                m.importance,
                m.confidence,
                m.status,
                i.search_text,
                bm25(memory_index_fts) AS bm25_score
            FROM memory_index_fts f
            JOIN memory_index i
                ON i.id = f.rowid
            JOIN memory_items m
                ON m.id = i.memory_id
            LEFT JOIN entities e
                ON e.id = m.entity_id
            WHERE m.status = 'current'
            AND f.search_text MATCH :query
            ORDER BY
                bm25_score ASC,
                m.importance DESC,
                m.confidence DESC
            LIMIT :limit
        """)

        debug_event(
            "DB_SEARCH_MEMORY_INDEX",
            query=query,
            terms=terms,
            fts_query=fts_query,
            candidate_limit=candidate_limit,
            sql=str(sql),
            params={
                "query": fts_query,
                "limit": candidate_limit
            }
        )

        with self.session() as session:
            rows = session.execute(
                sql,
                {
                    "query": fts_query,
                    "limit": candidate_limit
                }
            ).mappings().all()

        scored = []

        normalized_query = normalize(query)

        for row in rows:
            item = dict(row)

            search_text = item.pop(
                "search_text",
                ""
            )

            bm25_score = item.pop(
                "bm25_score",
                0
            )

            lexical_score = self._score_search_text(
                search_text,
                terms,
                normalized_query
            )

            if lexical_score <= 0:
                continue

            item["_search_score"] = lexical_score
            item["_bm25_score"] = bm25_score

            scored.append(item)

        scored.sort(
            key=lambda item: (
                -item["_search_score"],
                item["_bm25_score"],
                -float(item.get("importance") or 0),
                -float(item.get("confidence") or 0)
            )
        )

        result = []

        for item in scored[:limit]:
            item.pop("_search_score", None)
            item.pop("_bm25_score", None)
            result.append(item)

        debug_event(
            "DB_SEARCH_MEMORY_INDEX_RESULT",
            query=query,
            terms=terms,
            rows_count=len(result),
            rows=result
        )

        return result

    def search_legacy(self, query, limit=10):
        terms = self._extract_search_terms(
            query,
            minimum_length=3
        )

        if not terms:
            return []

        conditions = []

        for term in terms:
            pattern = f"%{term}%"

            conditions.append(
                or_(
                    func.lower(
                        func.coalesce(
                            MemoryItem.predicate,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            MemoryItem.value,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            Entity.name,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            EntityAlias.alias,
                            ""
                        )
                    ).like(pattern)
                )
            )

        stmt = (
            select(
                MemoryItem.id,
                Entity.name.label("entity"),
                MemoryItem.kind,
                MemoryItem.predicate,
                MemoryItem.value,
                MemoryItem.value_type,
                MemoryItem.object_entity_id,
                MemoryItem.importance,
                MemoryItem.confidence,
                MemoryItem.status
            )
            .distinct()
            .outerjoin(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .outerjoin(
                EntityAlias,
                EntityAlias.entity_id == MemoryItem.entity_id
            )
            .where(
                MemoryItem.status == "current",
                or_(*conditions)
            )
            .order_by(
                MemoryItem.importance.desc(),
                MemoryItem.confidence.desc()
            )
            .limit(limit)
        )

        debug_event(
            "DB_SEARCH_MEMORY",
            query=query,
            terms=terms,
            sql=str(stmt)
        )

        with self.session() as session:
            rows = session.execute(
                stmt
            ).mappings().all()

        result = [
            dict(row)
            for row in rows
        ]

        debug_event(
            "DB_SEARCH_MEMORY_RESULT",
            query=query,
            rows_count=len(result),
            rows=result
        )

        return result

    def current_for_entity(self, entity_id, limit=20):
        stmt = (
            select(
                MemoryItem.id,
                Entity.name.label("entity"),
                MemoryItem.kind,
                MemoryItem.predicate,
                MemoryItem.value,
                MemoryItem.value_type,
                MemoryItem.object_entity_id,
                MemoryItem.importance,
                MemoryItem.confidence,
                MemoryItem.status
            )
            .outerjoin(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .where(
                MemoryItem.entity_id == entity_id,
                MemoryItem.status == "current"
            )
            .order_by(
                MemoryItem.importance.desc(),
                MemoryItem.confidence.desc()
            )
            .limit(limit)
        )

        debug_event(
            "DB_CURRENT_MEMORIES",
            entity_id=entity_id,
            limit=limit,
            sql=str(stmt)
        )

        with self.session() as session:
            rows = session.execute(
                stmt
            ).mappings().all()

        result = [
            dict(row)
            for row in rows
        ]

        debug_event(
            "DB_CURRENT_MEMORIES_RESULT",
            entity_id=entity_id,
            rows_count=len(result),
            rows=result
        )

        return result

    def current_all(self, limit=20):
        stmt = (
            select(
                MemoryItem.id,
                Entity.name.label("entity"),
                MemoryItem.kind,
                MemoryItem.predicate,
                MemoryItem.value,
                MemoryItem.value_type,
                MemoryItem.object_entity_id,
                MemoryItem.importance,
                MemoryItem.confidence,
                MemoryItem.status
            )
            .outerjoin(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .where(
                MemoryItem.status == "current"
            )
            .order_by(
                MemoryItem.importance.desc(),
                MemoryItem.confidence.desc()
            )
            .limit(limit)
        )

        debug_event(
            "DB_ALL_CURRENT_MEMORIES",
            limit=limit,
            sql=str(stmt)
        )

        with self.session() as session:
            rows = session.execute(
                stmt
            ).mappings().all()

        result = [
            dict(row)
            for row in rows
        ]

        debug_event(
            "DB_ALL_CURRENT_MEMORIES_RESULT",
            rows_count=len(result),
            rows=result
        )

        return result

    def get_current_memories(self, entity_id, limit=20):
        return self.current_for_entity(
            entity_id=entity_id,
            limit=limit
        )

    def count_current_memories(self, entity_id=None):
        stmt = (
            select(
                func.count(MemoryItem.id)
            )
            .where(
                MemoryItem.status == "current"
            )
        )

        if entity_id is not None:
            stmt = stmt.where(
                MemoryItem.entity_id == entity_id
            )

        with self.session() as session:
            return int(
                session.scalar(stmt) or 0
            )

    def count_search(self, query, entity_id=None):
        terms = self._extract_search_terms(
            query,
            minimum_length=2
        )

        if not terms:
            return 0

        conditions = []

        for term in terms:
            pattern = f"%{term}%"

            conditions.append(
                or_(
                    func.lower(
                        func.coalesce(
                            MemoryItem.predicate,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            MemoryItem.value,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            Entity.name,
                            ""
                        )
                    ).like(pattern),
                    func.lower(
                        func.coalesce(
                            EntityAlias.alias,
                            ""
                        )
                    ).like(pattern)
                )
            )

        stmt = (
            select(
                func.count(
                    distinct(MemoryItem.id)
                )
            )
            .select_from(MemoryItem)
            .outerjoin(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .outerjoin(
                EntityAlias,
                EntityAlias.entity_id == MemoryItem.entity_id
            )
            .where(
                MemoryItem.status == "current",
                or_(*conditions)
            )
        )

        if entity_id is not None:
            stmt = stmt.where(
                MemoryItem.entity_id == entity_id
            )

        with self.session() as session:
            return int(
                session.scalar(stmt) or 0
            )

    def get_related_memories(self, entity_id, limit=20):
        stmt = (
            select(
                MemoryItem.id,
                Entity.name.label("entity"),
                MemoryItem.kind,
                MemoryItem.predicate,
                MemoryItem.value,
                MemoryItem.value_type,
                MemoryItem.object_entity_id,
                MemoryItem.importance,
                MemoryItem.confidence,
                MemoryItem.status
            )
            .join(
                Entity,
                Entity.id == MemoryItem.entity_id
            )
            .where(
                MemoryItem.status == "current",
                or_(
                    MemoryItem.entity_id == entity_id,
                    MemoryItem.object_entity_id == entity_id
                )
            )
            .order_by(
                MemoryItem.importance.desc(),
                MemoryItem.confidence.desc()
            )
            .limit(limit)
        )

        debug_event(
            "DB_RELATED_MEMORIES",
            entity_id=entity_id,
            limit=limit,
            sql=str(stmt)
        )

        with self.session() as session:
            rows = session.execute(
                stmt
            ).mappings().all()

        result = [
            dict(row)
            for row in rows
        ]

        debug_event(
            "DB_RELATED_MEMORIES_RESULT",
            entity_id=entity_id,
            rows_count=len(result),
            rows=result
        )

        return result