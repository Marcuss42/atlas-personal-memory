import re
import unicodedata

from .query import MemoryQueryPlan


class MemoryQueryRouter:
    _SELF_WORDS = {
        "eu",
        "me",
        "mim",
        "meu",
        "minha",
        "meus",
        "minhas",
        "comigo"
    }

    _TEMPORAL_WORDS = {
        "atual",
        "atualmente",
        "hoje"
    }

    def route(self, query: str) -> MemoryQueryPlan:
        text = self._normalize(query)

        relation = self._extract_relation(text)

        if relation:
            entity_hint, predicate, direction, object_hint = relation

            return self._build_plan(
                query=query,
                action=(
                    "count"
                    if self._is_relation_count(text)
                    else "related"
                ),
                entity_hint=entity_hint,
                predicate=predicate,
                direction=direction,
                object_hint=object_hint
            )

        scope = self._detect_scope(text)

        entity_hint = (
            self._extract_entity(text)
            if scope == "entity"
            else None
        )

        if self._is_count(text):
            count_entity = self._extract_count_entity(text)

            if count_entity:
                return MemoryQueryPlan(
                    action="search",
                    scope="entity",
                    query=query,
                    entity_hint=count_entity
                )

            return MemoryQueryPlan(
                action="count",
                scope=scope,
                query=query,
                entity_hint=entity_hint
            )

        if self._is_related(text):
            return MemoryQueryPlan(
                action="related",
                scope=scope,
                query=query,
                entity_hint=entity_hint
            )

        if self._is_list(text):
            return MemoryQueryPlan(
                action="list",
                scope=scope,
                query=query,
                entity_hint=entity_hint
            )

        return MemoryQueryPlan(
            action="search",
            scope=scope,
            query=query,
            entity_hint=entity_hint
        )

    def _build_plan(
        self,
        query,
        action,
        entity_hint,
        predicate,
        direction,
        object_hint=None
    ):
        if entity_hint in self._SELF_WORDS:
            scope = "self"
            entity_hint = None

        elif entity_hint:
            scope = "entity"

        else:
            scope = (
                "self"
                if self._has_self(
                    self._normalize(query)
                )
                else "global"
            )

        return MemoryQueryPlan(
            action=action,
            scope=scope,
            query=query,
            entity_hint=entity_hint,
            predicate=predicate,
            object_hint=object_hint,
            relation_direction=direction
        )

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize(
            "NFKD",
            text
        )

        text = "".join(
            char
            for char in text
            if not unicodedata.combining(char)
        )

        text = text.lower()

        text = re.sub(
            r"[^\w\s]",
            " ",
            text,
            flags=re.UNICODE
        )

        return re.sub(
            r"\s+",
            " ",
            text
        ).strip()

    @classmethod
    def _detect_scope(cls, text: str) -> str:
        if cls._has_self(text):
            return "self"

        if re.search(
            r"\bsobre\s+(?:o|a|um|uma)?\s*[\w-]+",
            text
        ):
            return "entity"

        if re.match(
            r"^o que\s+.+$",
            text
        ):
            return "entity"

        if re.match(
            r"^(?:qual|quais)\s+.+\s+"
            r"(?:o|a|os|as)\s+.+\s+\w+$",
            text
        ):
            return "entity"

        if re.match(
            r"^(?:quantos|quantas)\s+.+\s+.+\s+(?:tem|possui)$",
            text
        ):
            return "entity"

        return "global"

    @classmethod
    def _extract_entity(
        cls,
        text: str
    ) -> str | None:
        patterns = (
            r"\bsobre\s+(?:o|a|um|uma)\s+(.+)$",
            r"\bsobre\s+(.+)$",
            r"^o que\s+(.+?)\s+\w+$"
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                text
            )

            if match:
                entity = cls._clean_entity(
                    match.group(1)
                )

                if entity:
                    return entity

        match = re.match(
            r"^(?:qual|quais)\s+.+?\s+"
            r"(?:o|a|os|as)\s+(.+?)\s+\w+$",
            text
        )

        if match:
            return cls._clean_entity(
                match.group(1)
            )

        match = re.match(
            r"^(?:quantos|quantas)\s+.+?\s+"
            r"(.+?)\s+(?:tem|possui)$",
            text
        )

        if match:
            return cls._clean_entity(
                match.group(1)
            )

        return None

    @classmethod
    def _extract_count_entity(
        cls,
        text: str
    ) -> str | None:
        match = re.match(
            r"^(?:quantos|quantas)\s+.+?\s+"
            r"(.+?)\s+(?:tem|possui)$",
            text
        )

        if not match:
            return None

        entity = cls._clean_entity(
            match.group(1)
        )

        if entity in cls._SELF_WORDS:
            return None

        return entity

    @classmethod
    def _extract_relation(
        cls,
        text: str
    ) -> tuple[
        str | None,
        str | None,
        str,
        str | None
    ] | None:

        match = re.match(
            r"^quem\s+(?:e|sao)\s+(.+?)\s+de\s+(.+)$",
            text
        )

        if match:
            return (
                cls._clean_entity(
                    match.group(2)
                ),
                cls._normalize_predicate(
                    match.group(1)
                ),
                "object",
                None
            )

        # Exemplo:
        # "qual é a cor do objeto-007?"
        # "qual é a porta do servidor-004?"
        # "qual a idade da pessoa-003?"
        #
        # Deve resultar em:
        # entity_hint = objeto-007
        # predicate   = cor
        # direction   = object

        match = re.match(
            r"^(?:qual|quais)\s+"
            r"(?:e|sao)?\s*"
            r"(?:o|a|os|as)?\s*"
            r"(.+?)\s+"
            r"(?:do|da|dos|das|de)\s+"
            r"(.+)$",
            text
        )

        if match:
            predicate = cls._normalize_predicate(
                match.group(1)
            )

            entity = cls._clean_entity(
                match.group(2)
            )

            if predicate and entity:
                return (
                    entity,
                    predicate,
                    "object",
                    None
                )

        match = re.match(
            r"^(?:qual|quais)\s+(?:e|sao)?\s*"
            r"(?:o|a|os|as)?\s*(.+?)\s+de\s+(.+)$",
            text
        )

        if match:
            return (
                cls._clean_entity(
                    match.group(2)
                ),
                cls._normalize_predicate(
                    match.group(1)
                ),
                "object",
                None
            )

        # Exemplos:
        # "qual tecnologia o projeto-003 usa atualmente?"
        # "qual linguagem o projeto-010 utiliza?"
        #
        # Deve resultar em:
        # entity_hint = projeto-003
        # predicate   = usa
        # direction   = subject
        # object_hint = tecnologia

        match = re.match(
            r"^(?:qual|quais)\s+(.+?)\s+"
            r"(?:o|a|os|as)\s+(.+?)\s+"
            r"(\w+)"
            r"(?:\s+(?:atual|atualmente|hoje))?$",
            text
        )

        if match:
            object_hint = cls._clean_object_hint(
                match.group(1)
            )

            entity_hint = cls._clean_entity(
                match.group(2)
            )

            predicate = cls._normalize_predicate(
                match.group(3)
            )

            if entity_hint and predicate:
                return (
                    entity_hint,
                    predicate,
                    "subject",
                    object_hint
                )

        match = re.match(
            r"^(.+?)\s+(?:e|sao)\s+(.+?)\s+de\s+quem$",
            text
        )

        if match:
            return (
                cls._clean_entity(
                    match.group(1)
                ),
                cls._normalize_predicate(
                    match.group(2)
                ),
                "subject",
                None
            )

        match = re.match(
            r"^quem\s+(.+?)\s+(.+)$",
            text
        )

        if match:
            predicate = cls._normalize_predicate(
                match.group(1)
            )

            entity = cls._clean_entity(
                match.group(2)
            )

            if predicate and entity:
                return (
                    entity,
                    predicate,
                    "object",
                    None
                )

        match = re.match(
            r"^o que\s+(.+?)\s+(\w+)$",
            text
        )

        if match:
            return (
                cls._clean_entity(
                    match.group(1)
                ),
                cls._normalize_predicate(
                    match.group(2)
                ),
                "subject",
                None
            )

        self_count = cls._extract_self_count(
            text
        )

        if self_count:
            return (
                "eu",
                self_count,
                "subject",
                None
            )

        return None

    @staticmethod
    def _clean_object_hint(value: str) -> str:
        value = value.strip()

        value = re.sub(
            r"^(?:o|a|os|as|um|uma)\s+",
            "",
            value
        )

        return value.strip()

    @classmethod
    def _extract_self_count(
        cls,
        text: str
    ) -> str | None:
        match = re.match(
            r"^(?:quantos|quantas)\s+(.+?)\s+"
            r"eu\s+(?:tenho|possuo)$",
            text
        )

        if not match:
            return None

        return cls._normalize_predicate(
            match.group(1)
        )

    @classmethod
    def _is_relation_count(
        cls,
        text: str
    ) -> bool:
        return bool(
            re.match(
                r"^(?:quantos|quantas)\s+.+?\s+"
                r"eu\s+(?:tenho|possuo)$",
                text
            )
        )

    @staticmethod
    def _clean_entity(value: str) -> str:
        value = value.strip()

        value = re.sub(
            r"^(?:o|a|os|as|um|uma)\s+",
            "",
            value
        )

        return value.strip()

    @classmethod
    def _normalize_predicate(
        cls,
        value: str
    ) -> str:
        value = value.strip()

        words = value.split()

        while words and words[-1] in cls._TEMPORAL_WORDS:
            words.pop()

        value = " ".join(words)

        value = re.sub(
            r"^(?:o|a|os|as|um|uma)\s+",
            "",
            value
        )

        if value.endswith("ões"):
            value = value[:-3] + "ão"

        elif value.endswith("ães"):
            value = value[:-3] + "ão"

        elif value.endswith("ais"):
            value = value[:-3] + "al"

        elif value.endswith("éis"):
            value = value[:-3] + "el"

        elif value.endswith("óis"):
            value = value[:-3] + "ol"

        elif value.endswith("as"):
            value = value[:-2] + "a"

        elif value.endswith("os"):
            value = value[:-2] + "o"

        elif value.endswith("s"):
            value = value[:-1]

        return value

    @staticmethod
    def _is_count(text: str) -> bool:
        return bool(
            re.search(
                r"\bquantos?\b|"
                r"\bquantas?\b|"
                r"\bquantidade\b|"
                r"\bnumero\b|"
                r"\bnúmero\b",
                text
            )
        )

    @classmethod
    def _is_list(cls, text: str) -> bool:
        patterns = (
            r"\bquais\b",
            r"\bo que voce sabe\b",
            r"\bo que voce lembra\b",
            r"\bo que voce conhece\b",
            r"\bliste\b",
            r"\blistar\b",
            r"\bmostre\b",
            r"\bmostrar\b",
            r"\bfatos .*conhecimento\b"
        )

        return any(
            re.search(
                pattern,
                text
            )
            for pattern in patterns
        )

    @classmethod
    def _is_related(cls, text: str) -> bool:
        patterns = (
            r"\bde quem\b",
            r"^quem\s+",
            r"^o que\s+",
            r"\brelacao\b",
            r"\brelacoes\b",
            r"\brelacionad",
            r"\bligad",
            r"\bdepende\b",
            r"\bpertence\b"
        )

        return any(
            re.search(
                pattern,
                text
            )
            for pattern in patterns
        )