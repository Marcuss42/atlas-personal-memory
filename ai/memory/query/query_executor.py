import re

from ...logger import debug_event
from ...tools.memory_tools import buscar_memoria


class MemoryQueryExecutor:
    def __init__(self, memory):
        self.memory = memory

    def execute(self, plan):
        debug_event(
            "QUERY_EXECUTE_START",
            action=plan.action,
            scope=plan.scope,
            query=plan.query,
            entity_hint=plan.entity_hint,
            predicate=plan.predicate,
            object_hint=plan.object_hint,
            relation_direction=plan.relation_direction
        )

        entity_id = self._resolve_entity(plan)

        if plan.action == "list":
            result = self._list(
                plan,
                entity_id
            )

        elif plan.action == "count":
            result = self._count(
                plan,
                entity_id
            )

        elif plan.action == "related":
            result = self._related(
                plan,
                entity_id
            )

        else:
            result = self._search(
                plan,
                entity_id
            )

        debug_event(
            "QUERY_EXECUTE_COMPLETED",
            action=plan.action,
            entity_id=entity_id,
            results_count=len(result),
            results=result
        )

        return result

    def _resolve_entity(self, plan):
        if plan.scope == "self":
            return self.memory.user_entity_id

        if plan.scope != "entity":
            return None

        if not plan.entity_hint:
            return None

        entity_id = self.memory.find_entity_id(
            plan.entity_hint
        )

        debug_event(
            "QUERY_ENTITY_RESOLVE",
            entity_hint=plan.entity_hint,
            entity_id=entity_id
        )

        return entity_id

    def _list(self, plan, entity_id):
        if entity_id is not None:
            return self.memory.get_current_memories(
                entity_id,
                limit=plan.limit
            )

        return self.memory.get_all_current_memories(
            limit=plan.limit
        )

    def _count(self, plan, entity_id):
        if entity_id is None:
            return [
                {
                    "count": self.memory.count_memory_search(
                        plan.query
                    )
                }
            ]

        if plan.predicate:
            relation_count = self.memory.count_relations(
                entity_id=entity_id,
                predicate=plan.predicate,
                direction=plan.relation_direction
            )

            if relation_count > 0:
                return [
                    {
                        "count": relation_count,
                        "predicate": plan.predicate,
                        "type": "relation"
                    }
                ]

            memories = self._memories_by_predicate(
                entity_id,
                plan.predicate,
                plan.limit
            )

            if memories:
                return [
                    {
                        "value": memory.get("value"),
                        "predicate": memory.get("predicate"),
                        "value_type": memory.get("value_type"),
                        "type": "memory"
                    }
                    for memory in memories
                ]

        memories = self._rank_entity_memories(
            entity_id,
            plan.query,
            plan.limit
        )

        if memories:
            return [
                {
                    "value": memory.get("value"),
                    "predicate": memory.get("predicate"),
                    "value_type": memory.get("value_type"),
                    "type": "memory"
                }
                for memory in memories
            ]

        return [
            {
                "count": 0
            }
        ]

    def _related(self, plan, entity_id):
        if entity_id is not None:
            relations = self.memory.get_related_relations(
                entity_id=entity_id,
                predicate=None,
                direction=plan.relation_direction,
                limit=max(plan.limit, 50)
            )

            memories = self.memory.get_current_memories(
                entity_id,
                limit=max(plan.limit, 50)
            )

            ranked_relations = self._rank_relations(
                relations,
                plan,
                plan.limit
            )

            ranked_memories = self._rank_memories(
                memories,
                plan.query,
                plan.limit,
                entity_scope=True
            )

            result = self._merge_results(
                ranked_relations,
                ranked_memories,
                plan.limit
            )

            if result:
                return result

            return self._fallback_entity_results(
                relations,
                memories,
                plan.limit
            )

        return buscar_memoria(
            self.memory,
            plan.query
        )

    def _search(self, plan, entity_id):
        if entity_id is not None:
            relations = self.memory.get_related_relations(
                entity_id=entity_id,
                predicate=None,
                direction=plan.relation_direction,
                limit=max(plan.limit, 50)
            )

            memories = self.memory.get_current_memories(
                entity_id,
                limit=max(plan.limit, 50)
            )

            ranked_relations = self._rank_relations(
                relations,
                plan,
                plan.limit
            )

            ranked_memories = self._rank_memories(
                memories,
                plan.query,
                plan.limit,
                entity_scope=True
            )

            merged = self._merge_results(
                ranked_relations,
                ranked_memories,
                plan.limit
            )

            if merged:
                return merged

            fallback = self._fallback_entity_results(
                relations,
                memories,
                plan.limit
            )

            if fallback:
                return fallback

            debug_event(
                "QUERY_ENTITY_NO_RESULTS",
                entity_id=entity_id,
                entity_hint=plan.entity_hint,
                query=plan.query
            )

            return []

        return buscar_memoria(
            self.memory,
            plan.query
        )

    @staticmethod
    def _fallback_entity_results(
        relations,
        memories,
        limit
    ):
        result = []
        seen = set()

        for relation in relations:
            relation_id = relation.get("id")

            key = (
                "relation",
                relation_id
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(relation)

            if len(result) >= limit:
                return result

        ordered_memories = sorted(
            memories,
            key=lambda memory: (
                -float(
                    memory.get("importance") or 0
                ),
                -float(
                    memory.get("confidence") or 0
                )
            )
        )

        for memory in ordered_memories:
            memory_id = memory.get("id")

            key = (
                "memory",
                memory_id
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(memory)

            if len(result) >= limit:
                break

        return result

    @staticmethod
    def _merge_results(
        relations,
        memories,
        limit
    ):
        result = []
        seen = set()

        for relation in relations:
            relation_id = relation.get("id")

            key = (
                "relation",
                relation_id
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(relation)

            if len(result) >= limit:
                return result

        for memory in memories:
            memory_id = memory.get("id")

            key = (
                "memory",
                memory_id
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(memory)

            if len(result) >= limit:
                break

        return result

    @classmethod
    def _rank_relations(
        cls,
        relations,
        plan,
        limit
    ):
        if not relations:
            return []

        query_terms = cls._query_terms(
            plan.query
        )

        predicate = cls._normalize_term(
            plan.predicate
        )

        object_hint = cls._normalize_term(
            plan.object_hint
        )

        entity_hint = cls._normalize_term(
            plan.entity_hint
        )

        ranked = []

        for relation in relations:
            subject = cls._normalize_term(
                relation.get("subject")
            )

            relation_predicate = cls._normalize_term(
                relation.get("predicate")
            )

            object_name = cls._normalize_term(
                relation.get("object")
            )

            search_text = " ".join(
                value
                for value in (
                    subject,
                    relation_predicate,
                    object_name
                )
                if value
            )

            score = 0

            normalized_subject = cls._comparison_text(
                subject
            )

            normalized_entity = cls._comparison_text(
                entity_hint
            )

            if normalized_entity:
                if normalized_subject == normalized_entity:
                    score += 10
                elif (
                    normalized_entity in normalized_subject
                    or normalized_subject in normalized_entity
                ):
                    score += 5

            if predicate:
                normalized_relation_predicate = (
                    cls._comparison_text(
                        relation_predicate
                    )
                )

                normalized_predicate = (
                    cls._comparison_text(
                        predicate
                    )
                )

                if normalized_relation_predicate == normalized_predicate:
                    score += 8

                elif (
                    normalized_predicate
                    in normalized_relation_predicate
                ):
                    score += 4

                elif (
                    normalized_relation_predicate
                    in normalized_predicate
                ):
                    score += 2

            if object_hint:
                normalized_object = cls._comparison_text(
                    object_name
                )

                normalized_hint = cls._comparison_text(
                    object_hint
                )

                if normalized_object == normalized_hint:
                    score += 6

                elif (
                    normalized_hint in normalized_object
                    or normalized_object in normalized_hint
                ):
                    score += 3

            normalized_tokens = set(
                cls._comparison_text(
                    search_text
                ).split()
            )

            for term in query_terms:
                normalized_term = cls._comparison_text(
                    term
                )

                if normalized_term in normalized_tokens:
                    score += 1

            if score <= 0:
                continue

            ranked.append(
                (
                    score,
                    float(
                        relation.get("confidence") or 0
                    ),
                    float(
                        relation.get("importance") or 0
                    ),
                    relation
                )
            )

        ranked.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                -item[2]
            )
        )

        result = [
            item[3]
            for item in ranked[:limit]
        ]

        debug_event(
            "QUERY_RELATIONS_RANKED",
            entity_hint=plan.entity_hint,
            predicate=plan.predicate,
            object_hint=plan.object_hint,
            query=plan.query,
            candidates=len(relations),
            results_count=len(result),
            results=result
        )

        return result

    @staticmethod
    def _filter_predicate(
        memories,
        predicate
    ):
        normalized = str(
            predicate or ""
        ).strip().lower()

        return [
            memory
            for memory in memories
            if str(
                memory.get("predicate") or ""
            ).strip().lower() == normalized
        ]

    def _memories_by_predicate(
        self,
        entity_id,
        predicate,
        limit
    ):
        memories = self.memory.get_current_memories(
            entity_id,
            limit=max(limit, 20)
        )

        return self._filter_predicate(
            memories,
            predicate
        )[:limit]

    @staticmethod
    def _query_terms(query):
        words = str(
            query or ""
        ).lower()

        words = re.sub(
            r"[^\w\s-]",
            " ",
            words
        )

        return {
            word
            for word in words.split()
            if len(word) >= 3
        }

    @staticmethod
    def _normalize_term(value):
        value = str(
            value or ""
        ).strip().lower()

        value = re.sub(
            r"[^\w\s-]",
            " ",
            value
        )

        return re.sub(
            r"\s+",
            " ",
            value
        ).strip()

    @staticmethod
    def _comparison_text(value):
        value = str(
            value or ""
        ).strip().lower()

        value = value.replace(
            "-",
            " "
        ).replace(
            "_",
            " "
        )

        return re.sub(
            r"\s+",
            " ",
            value
        ).strip()

    @classmethod
    def _rank_memories(
        cls,
        memories,
        query,
        limit,
        entity_scope=False
    ):
        if not memories:
            return []

        terms = cls._query_terms(
            query
        )

        ranked = []

        for memory in memories:
            search_terms = memory.get(
                "search_terms",
                []
            )

            if not isinstance(
                search_terms,
                list
            ):
                search_terms = []

            fields = [
                memory.get("predicate"),
                memory.get("value")
            ] + search_terms

            text = " ".join(
                str(field)
                for field in fields
                if field is not None
            ).lower()

            tokens = set(
                re.findall(
                    r"\w+",
                    text
                )
            )

            score = 0

            for term in terms:
                if term in tokens:
                    score += 1

            normalized_query = cls._comparison_text(
                query
            )

            normalized_predicate = cls._comparison_text(
                memory.get("predicate")
            )

            normalized_value = cls._comparison_text(
                memory.get("value")
            )

            if normalized_predicate:
                if normalized_predicate in normalized_query:
                    score += 4

            if normalized_value:
                if normalized_value in normalized_query:
                    score += 3

            if entity_scope:
                score += 2

            ranked.append(
                (
                    score,
                    float(
                        memory.get("importance") or 0
                    ),
                    float(
                        memory.get("confidence") or 0
                    ),
                    memory
                )
            )

        ranked.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                -item[2]
            )
        )

        return [
            item[3]
            for item in ranked[:limit]
        ]

    def _rank_entity_memories(
        self,
        entity_id,
        query,
        limit
    ):
        memories = self.memory.get_current_memories(
            entity_id,
            limit=max(limit, 20)
        )

        return self._rank_memories(
            memories,
            query,
            limit,
            entity_scope=True
        )