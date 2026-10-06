import re
import unicodedata

from ...logger import debug_event


PRONOUNS = {
    "ele", "ela", "eles", "elas",
    "isso", "isto", "aquilo",
    "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas",
}

SELF_REFS = {
    "self", "eu", "me",
    "meu", "minha", "meus", "minhas",
    "comigo", "mim",
}

SCHEMA_KEYS = {
    "entities",
    "memories",
    "relations",
    "instructions",
}

CONTEXT_WORDS = {
    "sim", "não", "nao",
    "isso", "isto", "aquilo",
    "ele", "ela", "eles", "elas",
    "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas",
}


def normalize_text(text):
    text = unicodedata.normalize(
        "NFKD",
        str(text or "")
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


def slug(value):
    value = normalize_text(value)

    value = re.sub(
        r"[^\w\s-]",
        "",
        value
    )

    value = re.sub(
        r"[\s-]+",
        "_",
        value
    )

    return value.strip("_")


def normalize_ref(value):
    if not isinstance(value, str):
        return value

    value = value.strip()

    if not value:
        return value

    if value.lower() in SELF_REFS:
        return "self"

    return slug(value)


def clean_entity_name(value):
    value = str(value).strip()

    return re.sub(
        r"^(?:o|a|os|as|um|uma)\s+",
        "",
        value,
        flags=re.IGNORECASE
    ).strip()


def message_mentions(message, value):
    if not value:
        return False

    message = normalize_text(message)
    value = normalize_text(value)

    if not message or not value:
        return False

    return bool(
        re.search(
            rf"\b{re.escape(value)}\b",
            message,
            flags=re.UNICODE
        )
    )


def score(value, field):
    if value is None:
        raise ValueError(
            f"{field} não pode ser null."
        )

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{field} inválido: {value!r}"
        )

    if not 0 <= value <= 1:
        raise ValueError(
            f"{field} inválido: {value}"
        )

    return value


def _needs_context(message):
    text = normalize_text(message)

    if set(text.split()) & CONTEXT_WORDS:
        return True

    return bool(
        re.search(
            r"\b(?:meu|minha|meus|minhas|comigo|mim)\b",
            text
        )
    )


def _normalize_entities(extracted):
    entities = []
    entity_refs = set()

    for entity in extracted["entities"]:
        if not isinstance(entity, dict):
            raise ValueError(
                "Entidade inválida."
            )

        ref = entity.get("ref")
        name = entity.get("name")

        if not ref:
            raise ValueError(
                "Entidade sem ref."
            )

        if not name:
            raise ValueError(
                f"Entidade '{ref}' sem name."
            )

        ref = normalize_ref(ref)

        if ref == "self":
            continue

        name = clean_entity_name(name)

        if not name:
            raise ValueError(
                f"Entidade '{ref}' sem name."
            )

        if name.lower() in PRONOUNS:
            raise ValueError(
                f"Pronome não pode ser entidade: {name}"
            )

        aliases = entity.get(
            "aliases",
            []
        )

        if not isinstance(aliases, list):
            aliases = []

        aliases = [
            alias.strip()
            for alias in aliases
            if (
                isinstance(alias, str)
                and alias.strip()
                and alias.strip().lower()
                not in PRONOUNS
                and alias.strip().lower()
                not in SELF_REFS
                and alias.strip().lower()
                != name.lower()
            )
        ]

        entity["ref"] = ref
        entity["name"] = name
        entity["aliases"] = aliases

        if ref in entity_refs:
            continue

        entity_refs.add(ref)
        entities.append(entity)

    extracted["entities"] = entities

    return entities, entity_refs


def _normalize_memories(
    extracted,
    message,
    entities
):
    has_context = _needs_context(message)
    memories = []

    for memory in extracted["memories"]:
        if not isinstance(memory, dict):
            raise ValueError(
                "Memória inválida."
            )

        subject_ref = normalize_ref(
            memory.get("subject_ref")
        )

        if not subject_ref:
            raise ValueError(
                "Memória sem subject_ref."
            )

        value = memory.get("value")

        if isinstance(value, list):
            raise ValueError(
                "Memória não pode possuir value como lista."
            )

        if memory.get("object_ref"):
            raise ValueError(
                "Memória com object_ref deve ser "
                "representada como relation."
            )

        predicate = memory.get("predicate")

        if not predicate:
            raise ValueError(
                "Memória sem predicate."
            )

        memory["subject_ref"] = subject_ref
        memory["predicate"] = str(
            predicate
        ).strip()

        memory["value_type"] = memory.get(
            "value_type",
            "text"
        )

        memory["importance"] = score(
            memory.get(
                "importance",
                0.5
            ),
            "Importance"
        )

        memory["confidence"] = score(
            memory.get(
                "confidence",
                0.5
            ),
            "Confidence"
        )

        if subject_ref != "self" and not has_context:
            subject = next(
                (
                    entity
                    for entity in entities
                    if entity["ref"] == subject_ref
                ),
                None
            )

            if (
                subject
                and not message_mentions(
                    message,
                    subject["name"]
                )
            ):
                debug_event(
                    "EXTRACTION_SKIP_MEMORY_NOT_IN_MESSAGE",
                    subject_ref=subject_ref,
                    subject=subject["name"],
                    predicate=memory["predicate"]
                )
                continue

        memories.append(memory)

    extracted["memories"] = memories

    return memories


def _normalize_relations(extracted):
    relations = []

    for relation in extracted["relations"]:
        if not isinstance(relation, dict):
            raise ValueError(
                "Relação inválida."
            )

        subject_ref = normalize_ref(
            relation.get("subject_ref")
            or relation.get("subject")
            or relation.get("sub")
        )

        object_ref = normalize_ref(
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
                "Relação sem subject_ref."
            )

        if not object_ref:
            raise ValueError(
                "Relação sem object_ref."
            )

        if not predicate:
            raise ValueError(
                "Relação sem predicate."
            )

        relations.append({
            "subject_ref": subject_ref,
            "predicate": str(
                predicate
            ).strip(),
            "object_ref": object_ref,
            "symmetric": bool(
                relation.get(
                    "symmetric",
                    False
                )
            ),
            "confidence": score(
                relation.get(
                    "confidence",
                    0.5
                ),
                "Confidence"
            ),
            "resolution": relation.get(
                "resolution"
            )
        })

    extracted["relations"] = relations

    return relations


def _extract_entity_mentions(message):
    """
    Extrai candidatos a entidade diretamente da mensagem.

    A ideia não é tentar entender semanticamente a frase.
    Apenas identifica trechos que podem corresponder a uma
    referência normalizada.

    Exemplo:

        "O Objeto-002 é azul."

    produz:

        ("Objeto-002", "objeto_002")
    """

    text = str(message or "").strip()

    if not text:
        return []

    candidates = []

    patterns = (
        r"\b[A-ZÀ-Ý][\wÀ-ÿ]*(?:[-_][\wÀ-ÿ]+)+\b",
        r"\b[A-ZÀ-Ý][\wÀ-ÿ]*\d+\b",
    )

    for pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            flags=re.UNICODE
        ):
            name = clean_entity_name(
                match.group(0)
            )

            ref = slug(name)

            if not name or not ref:
                continue

            if name.lower() in PRONOUNS:
                continue

            candidates.append(
                (name, ref)
            )

    unique = []
    seen = set()

    for name, ref in candidates:
        if ref in seen:
            continue

        seen.add(ref)
        unique.append(
            (name, ref)
        )

    return unique


def _find_entity_name_in_message(
    message,
    ref
):
    """
    Tenta localizar na mensagem o nome correspondente a uma
    referência normalizada.

    Exemplos:

        ref = "redis"
        mensagem = "... usa Redis."
        -> "Redis"

        ref = "projeto_002"
        mensagem = "... Projeto-002 ..."
        -> "Projeto-002"

    A busca é usada somente para referências que o próprio
    extractor já declarou como entidade.
    """

    target = normalize_text(
        str(ref or "").replace("_", " ")
    )

    if not target:
        return None

    parts = target.split()

    pattern = (
        r"(?<!\w)"
        + r"[\s_-]+".join(
            re.escape(part)
            for part in parts
        )
        + r"(?!\w)"
    )

    match = re.search(
        pattern,
        str(message or ""),
        flags=re.IGNORECASE | re.UNICODE
    )

    if not match:
        return None

    return match.group(0).strip()


def _ensure_referenced_entities(
    extracted,
    message
):
    """
    Cria entidades ausentes somente quando a referência pode
    ser comprovada diretamente pela mensagem original.

    Isso evita depender do LLM para repetir a entidade na lista
    "entities".

    Exemplo válido:

        mensagem:
            "O Objeto-002 é azul."

        memória:
            subject_ref = "objeto_002"

        mesmo que o LLM não tenha retornado a entidade,
        podemos reconstruí-la porque "Objeto-002" aparece
        explicitamente na mensagem.
    """

    existing_refs = {
        entity["ref"]
        for entity in extracted["entities"]
    }

    referenced_refs = set()

    for memory in extracted["memories"]:
        ref = memory.get("subject_ref")

        if ref and ref != "self":
            referenced_refs.add(ref)

    for relation in extracted["relations"]:
        for ref in (
            relation.get("subject_ref"),
            relation.get("object_ref")
        ):
            if ref and ref != "self":
                referenced_refs.add(ref)

    missing_refs = (
        referenced_refs - existing_refs
    )

    if not missing_refs:
        return extracted

    candidates = _extract_entity_mentions(
        message
    )

    candidates_by_ref = {
        ref: name
        for name, ref in candidates
    }

    for ref in sorted(missing_refs):
        name = candidates_by_ref.get(ref)

        if not name:
            name = _find_entity_name_in_message(
                message,
                ref
            )

        if not name:
            continue

        extracted["entities"].append({
            "ref": ref,
            "name": name,
            "type": "unknown",
            "aliases": []
        })

        existing_refs.add(ref)

        debug_event(
            "EXTRACTION_CREATE_ENTITY_FROM_MESSAGE",
            ref=ref,
            name=name,
            reason=(
                "referenced_entity_missing_from_model_output"
                " | explicit_message_match"
            )
        )

    return extracted


def _filter_relations(
    relations,
    entities,
    message
):
    if _needs_context(message):
        return relations

    entity_by_ref = {
        entity["ref"]: entity
        for entity in entities
    }

    filtered = []

    for relation in relations:
        supported = True

        for ref in (
            relation["subject_ref"],
            relation["object_ref"]
        ):
            if ref == "self":
                continue

            entity = entity_by_ref.get(ref)

            if not entity:
                supported = False
                break

            if not message_mentions(
                message,
                entity["name"]
            ):
                supported = False
                break

        if supported:
            filtered.append(relation)
        else:
            debug_event(
                "EXTRACTION_SKIP_RELATION_NOT_IN_MESSAGE",
                relation=relation
            )

    return filtered


def _filter_entities(
    entities,
    memories,
    relations,
    message
):
    referenced = set()

    for memory in memories:
        if memory["subject_ref"] != "self":
            referenced.add(
                memory["subject_ref"]
            )

    for relation in relations:
        if relation["subject_ref"] != "self":
            referenced.add(
                relation["subject_ref"]
            )

        if relation["object_ref"] != "self":
            referenced.add(
                relation["object_ref"]
            )

    filtered = []

    for entity in entities:
        ref = entity["ref"]

        if ref in referenced:
            filtered.append(entity)
            continue

        name_supported = message_mentions(
            message,
            entity["name"]
        )

        alias_supported = any(
            message_mentions(
                message,
                alias
            )
            for alias in entity["aliases"]
        )

        if entity["aliases"] and (
            name_supported
            or alias_supported
        ):
            filtered.append(entity)
            continue

        debug_event(
            "EXTRACTION_SKIP_UNUSED_ENTITY",
            ref=ref,
            name=entity["name"]
        )

    return filtered


def _validate_references(
    entities,
    memories,
    relations
):
    entity_refs = {
        entity["ref"]
        for entity in entities
    }

    referenced = set()

    for memory in memories:
        if memory["subject_ref"] != "self":
            referenced.add(
                memory["subject_ref"]
            )

    for relation in relations:
        if relation["subject_ref"] != "self":
            referenced.add(
                relation["subject_ref"]
            )

        if relation["object_ref"] != "self":
            referenced.add(
                relation["object_ref"]
            )

    missing = referenced - entity_refs

    if missing:
        raise ValueError(
            "Referências sem entidade correspondente: "
            + ", ".join(
                sorted(missing)
            )
        )


def _remove_duplicate_relation_memories(
    memories,
    relations,
    entities
):
    entity_names = {
        entity["ref"]: entity["name"]
        for entity in entities
    }

    relation_keys = {
        (
            relation["subject_ref"],
            relation["predicate"].lower(),
            relation["object_ref"]
        )
        for relation in relations
    }

    filtered = []

    for memory in memories:
        subject_ref = memory["subject_ref"]
        predicate = memory["predicate"].lower()
        value = str(
            memory.get("value") or ""
        ).strip().lower()

        duplicate = False

        for (
            relation_subject,
            relation_predicate,
            relation_object
        ) in relation_keys:
            if relation_subject != subject_ref:
                continue

            if relation_predicate != predicate:
                continue

            object_name = str(
                entity_names.get(
                    relation_object,
                    ""
                )
            ).strip().lower()

            if value in {
                object_name,
                relation_object.lower()
            }:
                duplicate = True
                break

        if duplicate:
            debug_event(
                "EXTRACTION_SKIP_DUPLICATE_RELATION_MEMORY",
                subject_ref=subject_ref,
                predicate=memory["predicate"],
                value=memory.get("value")
            )
            continue

        filtered.append(memory)

    return filtered


def normalize_result(
    extracted,
    message=""
):
    if not isinstance(extracted, dict):
        raise ValueError(
            "Resultado da extração deve ser um objeto."
        )

    for key in SCHEMA_KEYS:
        extracted.setdefault(
            key,
            []
        )

        if not isinstance(
            extracted[key],
            list
        ):
            raise ValueError(
                f"{key} deve ser uma lista."
            )

    entities, _ = _normalize_entities(
        extracted
    )

    memories = _normalize_memories(
        extracted,
        message,
        entities
    )

    relations = _normalize_relations(
        extracted
    )

    extracted["relations"] = relations

    _ensure_referenced_entities(
        extracted,
        message
    )

    entities = extracted["entities"]

    _validate_references(
        entities,
        memories,
        relations
    )

    relations = _filter_relations(
        relations,
        entities,
        message
    )

    extracted["relations"] = relations

    entities = _filter_entities(
        entities,
        memories,
        relations,
        message
    )

    extracted["entities"] = entities

    _validate_references(
        entities,
        memories,
        relations
    )

    extracted["memories"] = (
        _remove_duplicate_relation_memories(
            memories,
            relations,
            entities
        )
    )

    return extracted


def apply_self_identity(
    extracted,
    message
):
    text = message.strip()

    patterns = (
        r"^eu\s+sou\s+(?:o|a)?\s*(.+)$",
        r"^(?:eu\s+me\s+chamo|meu\s+nome\s+(?:e|é))\s+"
        r"(?:o|a)?\s*(.+)$"
    )

    name = None

    for pattern in patterns:
        match = re.match(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:
            name = clean_entity_name(
                match.group(1)
            )
            break

    if not name:
        return extracted

    removed_refs = set()
    remaining_entities = []

    for entity in extracted["entities"]:
        entity_name = str(
            entity.get("name") or ""
        ).strip()

        if entity_name.lower() == name.lower():
            removed_refs.add(
                entity["ref"]
            )
            continue

        remaining_entities.append(entity)

    extracted["entities"] = remaining_entities

    for memory in extracted["memories"]:
        if memory.get("subject_ref") in removed_refs:
            memory["subject_ref"] = "self"

    for relation in extracted["relations"]:
        if relation.get("subject_ref") in removed_refs:
            relation["subject_ref"] = "self"

        if relation.get("object_ref") in removed_refs:
            relation["object_ref"] = "self"

    has_name_memory = any(
        memory.get("subject_ref") == "self"
        and str(
            memory.get("predicate") or ""
        ).lower() == "nome"
        for memory in extracted["memories"]
    )

    if not has_name_memory:
        extracted["memories"].append({
            "subject_ref": "self",
            "kind": "fact",
            "predicate": "nome",
            "value": name,
            "value_type": "text",
            "importance": 0.9,
            "confidence": 1.0,
            "search_terms": [
                "nome",
                name
            ]
        })

    return extracted


def apply_first_person_relation(
    extracted,
    message
):
    match = re.match(
        r"^eu\s+tenho\s+(?:um|uma)\s+(.+?)\s+"
        r"chamad[oa]\s+(.+)$",
        message.strip(),
        flags=re.IGNORECASE
    )

    if not match:
        return extracted

    predicate = re.sub(
        r"\s+",
        " ",
        match.group(1).strip()
    )

    name = clean_entity_name(
        match.group(2)
    )

    if not predicate or not name:
        return extracted

    ref = slug(name)
    existing_ref = None

    for entity in extracted["entities"]:
        if (
            str(
                entity.get("name") or ""
            ).lower() == name.lower()
        ):
            existing_ref = entity["ref"]
            break

    if existing_ref is None:
        existing_ref = ref

        existing_refs = {
            entity["ref"]
            for entity in extracted["entities"]
        }

        if existing_ref in existing_refs:
            index = 2

            while f"{ref}_{index}" in existing_refs:
                index += 1

            existing_ref = f"{ref}_{index}"

        extracted["entities"].append({
            "ref": existing_ref,
            "name": name,
            "type": "pessoa",
            "aliases": []
        })

    relation_exists = any(
        relation.get("subject_ref") == "self"
        and relation.get("object_ref")
        == existing_ref
        and str(
            relation.get("predicate") or ""
        ).strip().lower()
        == predicate.lower()
        for relation in extracted["relations"]
    )

    if not relation_exists:
        extracted["relations"].append({
            "subject_ref": "self",
            "predicate": predicate,
            "object_ref": existing_ref,
            "symmetric": (
                predicate.lower() == "amigo"
            ),
            "confidence": 1.0,
            "resolution": None
        })

    return extracted


def apply_deterministic_fixes(
    extracted,
    message
):
    extracted = apply_self_identity(
        extracted,
        message
    )

    return apply_first_person_relation(
        extracted,
        message
    )