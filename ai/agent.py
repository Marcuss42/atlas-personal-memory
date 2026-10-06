import os
from configparser import ConfigParser
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .logger import get_logger, get_error_logger, debug_event
from .memory.memory import MemoryStore
from .memory.extractor.extractor import MemoryExtractor
from .memory.persistence import MemoryPersister
from .memory.retriever import MemoryRetriever
from .response.generator import ResponseGenerator
from .rule_loader import load_rules


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

logger = get_logger("atlas.agent")
error_logger = get_error_logger()


def _log_error(
    event,
    message,
    exc,
    **data
):
    logger.error(
        "%s | %s",
        event,
        message
    )

    error_logger.exception(
        "%s | %s | error=%r | data=%r",
        event,
        message,
        exc,
        data
    )

    debug_event(
        event,
        error=repr(exc),
        **data
    )


def load_config():
    config = ConfigParser()
    path = BASE_DIR / "ai" / "config" / "config.ini"

    try:
        if not config.read(
            path,
            encoding="utf-8"
        ):
            raise FileNotFoundError(
                f"Configuração não encontrada: {path}"
            )

        debug_event(
            "CONFIG",
            config=str(path),
            response_model=config["model"]["response"],
            extraction_model=config["model"]["extraction"],
            response_max_tokens=config["model"]["response_max_tokens"],
            extraction_max_tokens=config["model"]["extraction_max_tokens"],
            reasoning_effort=config["model"]["reasoning_effort"],
            short_term_messages=config["agent"]["short_term_messages"],
            database=config["database"]["path"]
        )

        return config

    except Exception as exc:
        _log_error(
            "CONFIG_ERROR",
            "Erro carregando configuração",
            exc,
            config=str(path)
        )
        raise


class Atlas:
    def __init__(self):
        config = load_config()

        db_path = config["database"]["path"]

        try:
            self.memory = MemoryStore(
                db_path
            )

            debug_event(
                "DATABASE_INIT",
                configured_path=db_path,
                resolved_path=str(
                    self.memory.db_path
                )
            )

        except Exception as exc:
            _log_error(
                "DATABASE_INIT_ERROR",
                f"Erro inicializando banco | path={db_path}",
                exc,
                path=db_path
            )
            raise

        try:
            api_key = os.environ["OPENROUTER_API_KEY"]

            self.client = OpenAI(
                base_url=config["model"]["base_url"],
                api_key=api_key
            )

        except Exception as exc:
            _log_error(
                "CLIENT_INIT_ERROR",
                "Erro inicializando cliente OpenAI",
                exc
            )
            raise

        try:
            self.short_term_messages = int(
                config["agent"]["short_term_messages"]
            )

            if self.short_term_messages <= 0:
                raise ValueError(
                    "short_term_messages deve ser maior que zero"
                )

            response_rules = load_rules([
                "comportamento.txt",
                "resposta.txt"
            ])

            extraction_rules = load_rules([
                "memoria.txt",
                "conhecimento.txt",
                "contradicoes.txt",
                "instrucoes.txt"
            ])

            debug_event(
                "RULES",
                response_rules_chars=len(response_rules),
                extraction_rules_chars=len(extraction_rules)
            )

        except Exception as exc:
            _log_error(
                "RULES_ERROR",
                "Erro carregando regras",
                exc
            )
            raise

        try:
            self.extractor = MemoryExtractor(
                client=self.client,
                model=config["model"]["extraction"],
                max_tokens=int(
                    config["model"]["extraction_max_tokens"]
                ),
                rules=extraction_rules
            )

            self.persister = MemoryPersister(
                self.memory
            )

            self.retriever = MemoryRetriever(
                memory=self.memory
            )

            self.generator = ResponseGenerator(
                client=self.client,
                model=config["model"]["response"],
                max_tokens=int(
                    config["model"]["response_max_tokens"]
                ),
                reasoning_effort=config["model"]["reasoning_effort"],
                rules=response_rules,
                short_term_messages=self.short_term_messages
            )

        except Exception as exc:
            _log_error(
                "COMPONENTS_INIT_ERROR",
                "Erro inicializando componentes do Atlas",
                exc
            )
            raise

        debug_event(
            "ATLAS_INIT",
            response_model=config["model"]["response"],
            extraction_model=config["model"]["extraction"],
            short_term=self.short_term_messages,
            database=str(
                self.memory.db_path
            )
        )

    def process_message(
        self,
        conversation_id,
        message
    ):
        if conversation_id is None:
            raise ValueError(
                "conversation_id não pode ser None"
            )

        if not message or not message.strip():
            raise ValueError(
                "message não pode ser vazia"
            )

        message = message.strip()

        debug_event(
            "MESSAGE_RECEIVED",
            conversation_id=conversation_id,
            chars=len(message),
            message=message
        )

        try:
            message_id = self.memory.save_message(
                conversation_id,
                "user",
                message
            )

            debug_event(
                "MESSAGE_SAVED",
                conversation_id=conversation_id,
                message_id=message_id,
                sender="user"
            )

        except Exception as exc:
            _log_error(
                "MESSAGE_SAVE_ERROR",
                f"Erro salvando mensagem | conversation={conversation_id}",
                exc,
                conversation_id=conversation_id
            )
            raise

        try:
            recent_messages = self.memory.get_recent_messages(
                conversation_id,
                self.short_term_messages
            )

            context_messages = [
                item
                for item in recent_messages
                if item["id"] != message_id
            ]

            debug_event(
                "CONTEXT_LOADED",
                conversation_id=conversation_id,
                requested=self.short_term_messages,
                returned=len(context_messages),
                context_messages=context_messages
            )

        except Exception as exc:
            _log_error(
                "CONTEXT_ERROR",
                f"Erro carregando contexto | conversation={conversation_id}",
                exc,
                conversation_id=conversation_id
            )
            raise

        should_extract = False

        try:
            should_extract = self.extractor.should_extract(
                message,
                context_messages
            )

            debug_event(
                "EXTRACTION_DECISION",
                message_id=message_id,
                should_extract=should_extract,
                reason=(
                    "candidate"
                    if should_extract
                    else "not_candidate"
                )
            )

        except Exception as exc:
            _log_error(
                "EXTRACTION_DECISION_ERROR",
                f"Erro decidindo extração | message={message_id}",
                exc,
                message_id=message_id
            )

        if should_extract:
            try:
                extracted = self.extractor.extract(
                    message,
                    context_messages
                )

                debug_event(
                    "EXTRACTION_RESULT",
                    message_id=message_id,
                    result=extracted
                )

                self.persister.persist(
                    extracted,
                    message_id
                )

                debug_event(
                    "PERSISTENCE_COMPLETED",
                    message_id=message_id,
                    result=extracted
                )

            except Exception as exc:
                _log_error(
                    "EXTRACTION_ERROR",
                    f"Falha extraindo memória | message={message_id}",
                    exc,
                    message_id=message_id
                )

        else:
            debug_event(
                "EXTRACTION_SKIPPED",
                message_id=message_id
            )

        try:
            memories = self.retriever.retrieve(
                message,
                recent_messages
            )

            debug_event(
                "RETRIEVAL_RESULT",
                message_id=message_id,
                query=message,
                memories_count=len(memories),
                memories=memories
            )

        except Exception as exc:
            _log_error(
                "RETRIEVAL_ERROR",
                f"Erro recuperando memória | message={message_id}",
                exc,
                message_id=message_id,
                query=message
            )
            raise

        try:
            response = self.generator.generate(
                recent_messages,
                memories
            )

            if not response:
                raise RuntimeError(
                    "ResponseGenerator retornou resposta vazia ou None"
                )

            debug_event(
                "RESPONSE_GENERATED",
                conversation_id=conversation_id,
                chars=len(response),
                response=response
            )

        except Exception as exc:
            _log_error(
                "RESPONSE_GENERATION_ERROR",
                f"Erro gerando resposta | conversation={conversation_id}",
                exc,
                conversation_id=conversation_id
            )
            raise

        try:
            response_id = self.memory.save_message(
                conversation_id,
                "assistant",
                response
            )

            debug_event(
                "RESPONSE_SAVED",
                conversation_id=conversation_id,
                response_id=response_id
            )

            return response

        except Exception as exc:
            _log_error(
                "RESPONSE_SAVE_ERROR",
                f"Erro salvando resposta | conversation={conversation_id}",
                exc,
                conversation_id=conversation_id
            )
            raise