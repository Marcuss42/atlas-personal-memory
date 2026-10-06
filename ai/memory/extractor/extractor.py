import json
import re
import time

from ...logger import get_logger
from .extractor_normalizer import (
    apply_deterministic_fixes,
    normalize_result,
)
from .extractor_prompt import build_prompt


logger = get_logger("atlas.extractor")


class MemoryExtractor:
    _CONTEXT_WORDS = {
        "sim", "não", "nao",
        "isso", "isto", "aquilo",
        "ele", "ela", "eles", "elas",
        "esse", "essa", "esses", "essas",
        "aquele", "aquela", "aqueles", "aquelas",
    }

    def __init__(
        self,
        client,
        model,
        max_tokens,
        rules
    ):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.rules = rules

    @staticmethod
    def _normalize_text(text):
        import unicodedata

        text = unicodedata.normalize(
            "NFKD",
            str(text or "")
        )

        text = "".join(
            char for char in text
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

    def _format_context(self, recent_messages):
        if not recent_messages:
            return "Nenhum contexto recente."

        return "\n".join(
            f"{message['sender']}: {message['content']}"
            for message in recent_messages
        )

    def _needs_context(self, message):
        text = self._normalize_text(message)

        if set(text.split()) & self._CONTEXT_WORDS:
            return True

        return bool(
            re.search(
                r"\b(?:meu|minha|meus|minhas|comigo|mim)\b",
                text
            )
        )

    def should_extract(self, message, recent_messages=None):
        text = message.strip().lower()

        if not text or text.endswith("?"):
            return False

        if text in {
            "oi", "olá", "ola", "hey",
            "obrigado", "obrigada",
            "valeu", "beleza", "ok"
        }:
            return False

        question_words = (
            "qual ", "quais ", "quem ", "como ",
            "onde ", "quando ", "quanto ",
            "quantos ", "quantas ", "por que ",
            "porquê ", "porque "
        )

        return not text.startswith(question_words)

    @staticmethod
    def _clean_json_content(content):
        content = (content or "").strip()

        content = re.sub(
            r"^```json\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            r"^```\s*",
            "",
            content
        )

        content = re.sub(
            r"\s*```$",
            "",
            content
        )

        return content.strip()

    @classmethod
    def _parse(cls, content):
        content = cls._clean_json_content(content)
        start = content.find("{")

        if start == -1:
            raise ValueError("Nenhum JSON encontrado.")

        decoder = json.JSONDecoder()
        result, _ = decoder.raw_decode(content[start:])

        if not isinstance(result, dict):
            raise ValueError(
                "Resultado da extração não é um objeto JSON."
            )

        keys = {
            "entities",
            "memories",
            "relations",
            "instructions"
        }

        if keys & result.keys():
            result.pop("message", None)
            return result

        message = result.get("message")

        if isinstance(message, str):
            nested = cls._clean_json_content(message)
            nested_start = nested.find("{")

            if nested_start != -1:
                nested_result, _ = decoder.raw_decode(
                    nested[nested_start:]
                )

                if (
                    isinstance(nested_result, dict)
                    and keys & nested_result.keys()
                ):
                    nested_result.pop("message", None)
                    return nested_result

        raise ValueError(
            "JSON de extração não possui o schema esperado."
        )

    def _call_model(
        self,
        prompt,
        repair=False,
        max_tokens=None
    ):
        if repair:
            system_prompt = (
                "A resposta anterior falhou no formato. "
                "Gere novamente SOMENTE um objeto JSON válido. "
                "Use exatamente as chaves entities, memories, "
                "relations e instructions. "
                "Nunca retorne message."
            )
        else:
            system_prompt = (
                "Extraia conhecimento persistente. "
                "Retorne SOMENTE um objeto JSON válido. "
                "Use exatamente as chaves entities, memories, "
                "relations e instructions."
            )

        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=(
                max_tokens
                if max_tokens is not None
                else self.max_tokens
            ),
            response_format={
                "type": "json_object"
            }
        )

    def extract(self, message, recent_messages=None):
        recent_messages = recent_messages or []
        use_context = self._needs_context(message)

        context = (
            self._format_context(recent_messages)
            if use_context
            else "Contexto não necessário para esta mensagem."
        )

        prompt = build_prompt(
            message,
            context
        )

        logger.info(
            "Extração | model=%s | chars=%s | context_used=%s | "
            "context_chars=%s | prompt_chars=%s | max_tokens=%s",
            self.model,
            len(message),
            use_context,
            len(context),
            len(prompt),
            self.max_tokens
        )

        start = time.perf_counter()

        for attempt in range(2):
            retry_max_tokens = None

            if attempt == 1:
                retry_max_tokens = max(
                    self.max_tokens * 2,
                    800
                )

            response = self._call_model(
                prompt,
                repair=attempt == 1,
                max_tokens=retry_max_tokens
            )

            choice = response.choices[0]
            usage = getattr(response, "usage", None)

            logger.info(
                "Extração finish_reason | tentativa=%s | %s",
                attempt + 1,
                getattr(choice, "finish_reason", None)
            )

            logger.info(
                "Extração tokens | tentativa=%s | prompt=%s | "
                "completion=%s | total=%s | cost=%s",
                attempt + 1,
                getattr(usage, "prompt_tokens", 0),
                getattr(usage, "completion_tokens", 0),
                getattr(usage, "total_tokens", 0),
                getattr(usage, "cost", None)
            )

            content = getattr(
                choice.message,
                "content",
                None
            )

            try:
                extracted = self._parse(content)
                break
            except Exception:
                if attempt == 1:
                    logger.exception(
                        "Falha ao interpretar JSON da extração"
                    )
                    raise

                logger.warning(
                    "JSON inválido; solicitando nova geração"
                )

        extracted = normalize_result(
            extracted,
            message
        )

        extracted = apply_deterministic_fixes(
            extracted,
            message
        )

        extracted = normalize_result(
            extracted,
            message
        )

        logger.info(
            "Extração concluída | %.2fs | entities=%s | memories=%s | "
            "relations=%s | instructions=%s",
            time.perf_counter() - start,
            len(extracted["entities"]),
            len(extracted["memories"]),
            len(extracted["relations"]),
            len(extracted["instructions"])
        )

        return extracted