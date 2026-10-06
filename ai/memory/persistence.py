from ..logger import debug_event


class MemoryPersister:
    _SELF_REFS = {
        "self",
        "eu",
        "me",
        "meu",
        "minha",
        "meus",
        "minhas",
        "comigo",
        "mim"
    }

    _PRONOUN_ALIASES = {
        "ele",
        "ela",
        "eles",
        "elas",
        "isso",
        "isto",
        "aquilo",
        "esse",
        "essa",
        "esses",
        "essas",
        "aquele",
        "aquela",
        "aqueles",
        "aquelas"
    }

    _RESOLUTIONS = {
        None,
        "update",
        "correction"
    }

    def __init__(self, memory):
        self.memory = memory

    @classmethod
    def _normalize_ref(cls, ref):
        if not isinstance(ref, str):
            return ref

        ref = ref.strip()

        if ref.lower() in cls._SELF_REFS:
            return "self"

        return ref

    @staticmethod
    def _normalize_value(value):
        if not isinstance(value, str):
            return value

        return value.strip().lower()

    @staticmethod
    def _validate_score(value, field):
        value = float(value)

        if not 0 <= value <= 1:
            raise ValueError(
                f"{field} inválida: {value}"
            )

        return value

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

    def persist(
        self,
        extracted,
        source_message_id
    ):
        entity_refs = {
            "self": self.memory.user_entity_id
        }

        entity_names = {
            "self": "Usuário"
        }

        for entity in extracted.get(
            "entities",
            []
        ):
            ref = self._normalize_ref(
                entity.get("ref")
            )
            name = entity.get("name")

            if not ref:
                raise ValueError(
                    "Entidade extraída sem 'ref'"
                )

            if ref == "self":
                continue

            if not name:
                raise ValueError(
                    f"Entidade '{ref}' sem name"
                )

            name = name.strip()

            entity_id = self.memory.resolve_entity(
                name,
                entity.get("type")
            )

            entity_refs[ref] = entity_id
            entity_names[ref] = name

            for alias in entity.get(
                "aliases",
                []
            ):
                if not isinstance(alias, str):
                    continue

                alias = alias.strip()

                if not alias:
                    continue

                if alias.lower() in self._PRONOUN_ALIASES:
                    continue

                if alias.lower() in self._SELF_REFS:
                    continue

                if alias.lower() == name.lower():
                    continue

                self.memory.add_alias(
                    entity_id,
                    alias
                )

            debug_event(
                "ENTITY_RESOLVED",
                ref=ref,
                name=name,
                entity_id=entity_id
            )

        relations_data = extracted.get(
            "relations",
            []
        )

        relation_keys = set()

        for relation in relations_data:
            subject_ref = self._normalize_ref(
                relation.get("subject_ref")
                or relation.get("subject")
                or relation.get("sub")
            )

            object_ref = self._normalize_ref(
                relation.get("object_ref")
                or relation.get("object")
                or relation.get("obj")
            )

            predicate = (
                relation.get("predicate")
                or relation.get("rel")
            )

            if not subject_ref:
                raise ValueError(
                    "Relação sem subject_ref"
                )

            if not object_ref:
                raise ValueError(
                    "Relação sem object_ref"
                )

            if not predicate:
                raise ValueError(
                    "Relação sem predicate"
                )

            relation_keys.add(
                (
                    subject_ref,
                    predicate.strip().lower(),
                    object_ref
                )
            )

        memories = 0
        relations = 0
        instructions = 0

        for item in extracted.get(
            "memories",
            []
        ):
            subject_ref = self._normalize_ref(
                item.get("subject_ref")
            )

            subject_id = entity_refs.get(
                subject_ref
            )

            if subject_id is None:
                raise ValueError(
                    f"Memória subject ref não resolvido: {subject_ref}"
                )

            value = item.get("value")

            if isinstance(value, list):
                raise ValueError(
                    "Memória não pode possuir value como lista"
                )

            object_ref = item.get(
                "object_ref"
            )

            if object_ref:
                raise ValueError(
                    "Memória com object_ref deve ser representada como relation"
                )

            predicate = item.get("predicate")

            if not predicate:
                raise ValueError(
                    "Memória sem predicate"
                )

            normalized_predicate = predicate.strip().lower()
            normalized_value = self._normalize_value(value)

            duplicated_relation = False

            for (
                relation_subject,
                relation_predicate,
                relation_object
            ) in relation_keys:
                if relation_subject != subject_ref:
                    continue

                if relation_predicate != normalized_predicate:
                    continue

                object_name = self._normalize_value(
                    entity_names.get(relation_object)
                )

                object_ref_value = self._normalize_value(
                    relation_object
                )

                if normalized_value in {
                    object_name,
                    object_ref_value
                }:
                    duplicated_relation = True
                    break

            if duplicated_relation:
                debug_event(
                    "MEMORY_SKIPPED_DUPLICATE_RELATION",
                    subject_ref=subject_ref,
                    predicate=predicate,
                    value=value
                )
                continue

            importance = self._validate_score(
                item.get("importance", 0.5),
                "Importance"
            )

            confidence = self._validate_score(
                item.get("confidence", 0.5),
                "Confidence"
            )

            resolution = self._normalize_resolution(
                item.get("resolution")
            )

            self.memory.save_memory(
                subject_entity_id=subject_id,
                kind=item.get("kind", "fact"),
                predicate=predicate,
                value=value,
                value_type=item.get("value_type", "text"),
                object_entity_id=None,
                importance=importance,
                confidence=confidence,
                source_message_id=source_message_id,
                search_terms=item.get("search_terms", []),
                resolution=resolution
            )

            debug_event(
                "MEMORY_PERSISTED",
                subject_ref=subject_ref,
                predicate=predicate,
                value=value,
                resolution=resolution,
                source_message_id=source_message_id
            )

            memories += 1

        for relation in relations_data:
            subject_ref = self._normalize_ref(
                relation.get("subject_ref")
                or relation.get("subject")
                or relation.get("sub")
            )

            object_ref = self._normalize_ref(
                relation.get("object_ref")
                or relation.get("object")
                or relation.get("obj")
            )

            predicate = (
                relation.get("predicate")
                or relation.get("rel")
            )

            if not subject_ref:
                raise ValueError(
                    "Relação sem subject_ref"
                )

            if not object_ref:
                raise ValueError(
                    "Relação sem object_ref"
                )

            if not predicate:
                raise ValueError(
                    "Relação sem predicate"
                )

            subject_id = entity_refs.get(
                subject_ref
            )

            object_id = entity_refs.get(
                object_ref
            )

            if subject_id is None:
                raise ValueError(
                    f"Relation subject ref não resolvido: {subject_ref}"
                )

            if object_id is None:
                raise ValueError(
                    f"Relation object ref não resolvido: {object_ref}"
                )

            confidence = self._validate_score(
                relation.get("confidence", 0.5),
                "Confidence"
            )

            resolution = self._normalize_resolution(
                relation.get("resolution")
            )

            self.memory.save_relation(
                subject_entity_id=subject_id,
                predicate=predicate,
                object_entity_id=object_id,
                symmetric=bool(
                    relation.get("symmetric", False)
                ),
                confidence=confidence,
                source_message_id=source_message_id,
                resolution=resolution
            )

            relations += 1

        for instruction in extracted.get(
            "instructions",
            []
        ):
            if not isinstance(
                instruction,
                dict
            ):
                continue

            content = instruction.get(
                "content"
            )

            if not content:
                continue

            self.memory.save_instruction(
                content.strip(),
                source_message_id
            )

            instructions += 1

        debug_event(
            "PERSISTENCE_SUMMARY",
            message_id=source_message_id,
            memories=memories,
            relations=relations,
            instructions=instructions
        )

        return extracted