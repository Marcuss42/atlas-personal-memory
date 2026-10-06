from sqlalchemy import select

from ...logger import debug_event
from ..models.conversation_model import Conversation
from ..utils import utc_now
from .base_repository import BaseRepository


class ConversationRepository(BaseRepository):
    def create(self):
        conversation = Conversation(
            created_at=utc_now()
        )

        with self.session() as session:
            session.add(conversation)
            session.flush()

            conversation_id = conversation.id

        debug_event(
            "DB_CONVERSATION_CREATED",
            conversation_id=conversation_id
        )

        return conversation_id