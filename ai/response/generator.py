import json
import time

from ..logger import get_logger


logger = get_logger("atlas.response")


class ResponseGenerator:
    def __init__(
        self,
        client,
        model,
        max_tokens,
        reasoning_effort,
        rules,
        short_term_messages
    ):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.rules = rules
        self.short_term_messages = short_term_messages

    def _format_context(self, recent_messages):
        if not recent_messages:
            return "Nenhum contexto recente."

        return "\n".join(
            f"{message['sender']}: {message['content']}"
            for message in recent_messages
        )

    @staticmethod
    def _clean_content(content):
        content = (content or "").strip()

        if content.startswith("```json"):
            content = content[7:].strip()

        elif content.startswith("```"):
            content = content[3:].strip()

        if content.endswith("```"):
            content = content[:-3].strip()

        return content

    @staticmethod
    def _extract_message_from_json(content):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return content

        if not isinstance(parsed, dict):
            raise ValueError(
                "Resposta do modelo não é texto natural."
            )

        message = parsed.get("message")

        if isinstance(message, str) and message.strip():
            return message.strip()

        for key in (
            "response",
            "answer",
            "content",
            "text"
        ):
            value = parsed.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        raise ValueError(
            "Resposta JSON estruturada sem conteúdo textual."
        )

    def generate(
        self,
        recent_messages,
        memories
    ):
        context_messages = recent_messages[:-1]

        current_message = (
            recent_messages[-1]["content"]
            if recent_messages
            else ""
        )

        context_text = self._format_context(
            context_messages
        )

        memory_text = json.dumps(
            memories,
            ensure_ascii=False
        )

        system_prompt = f"""
Você é Atlas, um assistente pessoal.

A mensagem mais recente do usuário é a solicitação atual e deve ser
o foco principal da resposta.

Use a memória persistente fornecida como fonte de verdade para fatos
sobre o usuário e outras informações persistentes.

O contexto recente serve somente para manter continuidade e resolver
referências que dependam de mensagens anteriores.

REGRAS IMPORTANTES:

- Não invente informações.
- Memória vazia significa que nenhuma informação relevante foi encontrada.
- Não introduza assuntos anteriores que não sejam relevantes.
- Use o contexto recente somente quando necessário.
- Referências como "isso", "aquilo", "ele", "ela", "sim" e "não"
  devem usar o contexto quando houver relação clara.
- Uma mensagem sobre outro assunto deve ser tratada como outro assunto.
- A memória persistente tem prioridade sobre informações contraditórias
  presentes apenas no contexto recente.
- Não trate perguntas como afirmações.
- Considere a memória persistente atual como a fonte mais recente
  para fatos já confirmados ou atualizados.

FORMATO DA RESPOSTA:

- Responda somente em linguagem natural.
- Nunca retorne JSON.
- Nunca retorne dicionários, listas ou objetos estruturados.
- Nunca exponha IDs internos.
- Nunca exponha nomes de campos internos.
- Nunca copie registros da memória diretamente.
- Nunca use blocos de código.
- Não descreva a estrutura interna da memória.
- Não invente quando os dados forem insuficientes.
- Responda diretamente ao que o usuário perguntou.

REGRAS DE COMPORTAMENTO:

{self.rules}

CONTEXTO RECENTE:

{context_text}

MEMÓRIA PERSISTENTE:

{memory_text}
""".strip()

        logger.info(
            "Resposta | model=%s | context=%s | memories=%s | prompt_chars=%s",
            self.model,
            len(context_messages),
            len(memories),
            len(system_prompt)
        )

        logger.debug(
            "Resposta contexto | %r",
            context_text
        )

        logger.debug(
            "Memória enviada | %s",
            memory_text
        )

        logger.debug(
            "Mensagem atual | %r",
            current_message
        )

        start = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": current_message
                    }
                ],
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort
            )
        except Exception:
            logger.exception(
                "Erro gerando resposta"
            )
            raise

        choice = response.choices[0]

        logger.info(
            "Resposta finish_reason | %s",
            choice.finish_reason
        )

        usage = response.usage

        logger.info(
            "Resposta tokens | prompt=%s | completion=%s | reasoning=%s | total=%s",
            getattr(
                usage,
                "prompt_tokens",
                0
            ),
            getattr(
                usage,
                "completion_tokens",
                0
            ),
            getattr(
                getattr(
                    usage,
                    "completion_tokens_details",
                    None
                ),
                "reasoning_tokens",
                0
            ),
            getattr(
                usage,
                "total_tokens",
                0
            )
        )

        content = getattr(
            choice.message,
            "content",
            None
        )

        logger.debug(
            "Resposta modelo | %r",
            content
        )

        if not content:
            raise RuntimeError(
                "ResponseGenerator retornou resposta vazia."
            )

        content = self._clean_content(
            content
        )

        content = self._extract_message_from_json(
            content
        )

        if not content:
            raise RuntimeError(
                "ResponseGenerator produziu conteúdo vazio."
            )

        logger.info(
            "Resposta concluída | %.2fs | chars=%s",
            time.perf_counter() - start,
            len(content)
        )

        return content