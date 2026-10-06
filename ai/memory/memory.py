from pathlib import Path

from ..logger import debug_event
from .database import create_database, initialize_database, rebuild_memory_fts
from .repositories import (
    ConversationRepository,
    MessageRepository,
    EntityRepository,
    MemoryRepository,
    RelationRepository,
    InstructionRepository
)


class MemoryStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

        if not self.db_path.is_absolute():
            self.db_path = Path(__file__).resolve().parents[2] / self.db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        debug_event("MEMORY_INIT", configured_path=db_path, resolved_path=str(self.db_path.resolve()))

        self.engine, self.session_factory = create_database(self.db_path)
        initialize_database(self.engine)

        self.conversations = ConversationRepository(self.session_factory)
        self.messages = MessageRepository(self.session_factory)
        self.entities = EntityRepository(self.session_factory)
        self.memories = MemoryRepository(self.session_factory)
        self.relations = RelationRepository(self.session_factory)
        self.instructions = InstructionRepository(self.session_factory)

        self.user_entity_id = self.entities.ensure_user_entity()

        debug_event("MEMORY_READY", db=str(self.db_path.resolve()), user_entity_id=self.user_entity_id)

    def create_conversation(self):
        return self.conversations.create()

    def save_message(self, conversation_id, sender, content, metadata=None):
        return self.messages.save(conversation_id=conversation_id, sender=sender, content=content, metadata_json=metadata)

    def get_recent_messages(self, conversation_id, limit=10):
        return self.messages.recent(conversation_id, limit)

    def resolve_entity(self, name, entity_type=None):
        return self.entities.resolve(name, entity_type)

    def find_entity_id(self, name):
        return self.entities.find_by_name_or_alias(name)

    def add_alias(self, entity_id, alias):
        self.entities.add_alias(entity_id, alias)
        self.memories.refresh_entity_indexes(entity_id)

    def save_memory(self, subject_entity_id, kind, predicate, value, value_type, object_entity_id, importance, confidence, source_message_id, search_terms=None, resolution=None):
        return self.memories.save(
            subject_entity_id=subject_entity_id,
            kind=kind,
            predicate=predicate,
            value=value,
            value_type=value_type,
            object_entity_id=object_entity_id,
            importance=importance,
            confidence=confidence,
            source_message_id=source_message_id,
            search_terms=search_terms,
            resolution=resolution
        )

    def get_memory(self, memory_id):
        return self.memories.get(memory_id)

    def save_memory_index(self, memory_id, search_terms=None):
        return self.memories.save_index(memory_id, search_terms)

    def update_memory_index(self, memory_id, search_terms):
        return self.memories.update_index(memory_id, search_terms)

    def search_memory_index(self, query, limit=10):
        return self.memories.search_index(query, limit)

    def search_memory(self, query, limit=10):
        result = self.memories.search_index(query, limit)

        if result:
            return result

        return self.memories.search_legacy(query, limit)

    def get_current_memories(self, entity_id=None, limit=20):
        entity_id = entity_id if entity_id is not None else self.user_entity_id
        return self.memories.current_for_entity(entity_id, limit)

    def get_all_current_memories(self, limit=20):
        return self.memories.current_all(limit=limit)

    def count_current_memories(self, entity_id=None):
        return self.memories.count_current_memories(
            entity_id=entity_id if entity_id is not None else self.user_entity_id
        )

    def count_memory_search(self, query, entity_id=None):
        return self.memories.count_search(query=query, entity_id=entity_id)

    def get_related_memories(self, entity_id, limit=20):
        return self.memories.get_related_memories(entity_id=entity_id, limit=limit)

    def save_relation(self, subject_entity_id, predicate, object_entity_id, symmetric, confidence, source_message_id, resolution=None):
        return self.relations.save(
            subject_entity_id=subject_entity_id,
            predicate=predicate,
            object_entity_id=object_entity_id,
            symmetric=symmetric,
            confidence=confidence,
            source_message_id=source_message_id,
            resolution=resolution
        )

    def count_relations(self, entity_id=None, predicate=None, direction="both", subject_entity_id=None, object_entity_id=None):
        if subject_entity_id is not None:
            return self.relations.count_by_subject(subject_entity_id, predicate)

        if object_entity_id is not None:
            return self.relations.count_by_object(object_entity_id, predicate)

        if entity_id is None:
            return 0

        return self.relations.count_related(entity_id=entity_id, predicate=predicate, direction=direction)

    def get_related_relations(self, entity_id, predicate=None, direction="both", limit=20):
        return self.relations.find_related(entity_id=entity_id, predicate=predicate, direction=direction, limit=limit)

    def save_instruction(self, content, source_message_id):
        return self.instructions.save(content, source_message_id)

    def rebuild_memory_fts(self):
        rebuild_memory_fts(self.engine)