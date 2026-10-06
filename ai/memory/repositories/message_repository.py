from sqlalchemy import select

from ...logger import debug_event
from ..models.message_model import Message
from ..utils import utc_now
from .base_repository import BaseRepository


class MessageRepository(BaseRepository):
    model = Message

    def save(
        self,
        conversation_id: int,
        sender: str,
        content: str,
        created_at: str | None = None,
        metadata_json: str | None = None
    ) -> int:
        if conversation_id is None:
            raise ValueError(
                "conversation_id não pode ser None"
            )

        if not sender or not sender.strip():
            raise ValueError(
                "sender não pode ser vazio"
            )

        if content is None:
            raise ValueError(
                "content não pode ser None"
            )

        sender = sender.strip()

        if created_at is None:
            created_at = utc_now()

        with self.session() as session:
            message = Message(
                conversation_id=conversation_id,
                sender=sender,
                content=content,
                created_at=created_at,
                metadata_json=metadata_json
            )

            session.add(message)
            session.flush()

            message_id = message.id

        debug_event(
            "MESSAGE_SAVED",
            message_id=message_id,
            conversation_id=conversation_id,
            sender=sender
        )

        return message_id

    def find_by_id(
        self,
        message_id: int
    ) -> Message | None:
        if message_id is None:
            return None

        with self.session() as session:
            return session.get(
                Message,
                message_id
            )

    def recent(
        self,
        conversation_id: int,
        limit: int
    ) -> list[dict]:
        if conversation_id is None:
            return []

        if limit <= 0:
            return []

        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id
            )
            .order_by(
                Message.id.desc()
            )
            .limit(limit)
        )

        with self.session() as session:
            messages = list(
                session.scalars(stmt)
            )[::-1]

        result = [
            {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender": message.sender,
                "content": message.content,
                "created_at": message.created_at,
                "metadata": message.metadata_json
            }
            for message in messages
        ]

        debug_event(
            "MESSAGES_RECENT",
            conversation_id=conversation_id,
            limit=limit,
            rows_count=len(result)
        )

        return result