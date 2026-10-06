from sqlalchemy import select

from ...logger import debug_event
from ..models.instruction_model import Instruction
from ..utils import utc_now
from .base_repository import BaseRepository


class InstructionRepository(BaseRepository):
    def save(
        self,
        content,
        source_message_id
    ):
        if not content or not content.strip():
            raise ValueError(
                "Instrução não pode ser vazia"
            )

        content = content.strip()
        now = utc_now()

        with self.session() as session:
            existing = session.scalar(
                select(Instruction)
                .where(
                    Instruction.content == content,
                    Instruction.status == "active"
                )
                .limit(1)
            )

            if existing:
                existing.updated_at = now
                instruction_id = existing.id

                debug_event(
                    "INSTRUCTION_UNCHANGED",
                    instruction_id=instruction_id
                )

                return instruction_id

            instruction = Instruction(
                content=content,
                status="active",
                created_at=now,
                updated_at=now,
                source_message_id=source_message_id
            )

            session.add(instruction)
            session.flush()

            instruction_id = instruction.id

        debug_event(
            "INSTRUCTION_SAVED",
            instruction_id=instruction_id,
            source_message_id=source_message_id
        )

        return instruction_id