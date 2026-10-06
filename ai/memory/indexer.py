import json
import re

from ..logger import debug_event


class MemoryIndexer:
    def __init__(self, memory):
        self.memory = memory

    def _normalize_terms(self, terms):
        if not terms:
            return []

        result = []

        for term in terms:
            if not isinstance(term, str):
                continue

            term = re.sub(r"\s+", " ", term.strip().lower())

            if term and term not in result:
                result.append(term)

        return result

    def build_text(self, memory_item):
        terms = memory_item.get("search_terms", [])

        terms = self._normalize_terms(terms)

        predicate = memory_item.get("predicate")
        value = memory_item.get("value")
        entity = memory_item.get("subject_ref")

        fields = [
            entity,
            predicate,
            value,
            *terms
        ]

        return " ".join(
            str(field)
            for field in fields
            if field
        )

    def index(self, memory_id, memory_item):
        search_terms = self._normalize_terms(
            memory_item.get("search_terms", [])
        )

        search_text = self.build_text(
            memory_item
        )

        debug_event(
            "MEMORY_INDEX_START",
            memory_id=memory_id,
            search_terms=search_terms,
            search_text=search_text
        )

        self.memory.save_memory_index(
            memory_id=memory_id,
            search_text=search_text,
            search_terms=json.dumps(
                search_terms,
                ensure_ascii=False
            )
        )

        debug_event(
            "MEMORY_INDEX_COMPLETED",
            memory_id=memory_id,
            search_terms=search_terms,
            search_text=search_text
        )

    def update(self, memory_id, search_terms):
        search_terms = self._normalize_terms(
            search_terms
        )

        memory = self.memory.get_memory(
            memory_id
        )

        if not memory:
            raise ValueError(
                f"Memória não encontrada: {memory_id}"
            )

        memory["search_terms"] = search_terms

        self.index(
            memory_id,
            memory
        )