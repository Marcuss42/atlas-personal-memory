import json
import random
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.agent import Atlas


class Tester:
    def __init__(self, caso):
        base_dir = Path(__file__).resolve().parent
        self.caso = self._normalizar_caso(caso)
        self.caso_dir = self._localizar_diretorio_caso(base_dir)
        self.fatos_path = self.caso_dir / "fatos.json"

        if not self.fatos_path.is_file():
            raise FileNotFoundError(
                f"O arquivo fatos.json não foi encontrado em: {self.caso_dir}"
            )

        self.log_path = self.caso_dir / "tester.log"
        self.log_file = self.log_path.open("w", encoding="utf-8")

        self.aprendizados, self.testes = self._carregar_fatos()

        self.atlas = Atlas()
        self.learning_conversation_id = self.atlas.memory.create_conversation()
        self.test_conversation_id = self.atlas.memory.create_conversation()

        self.evaluator_model = "openai/gpt-oss-20b:nitro"

    @staticmethod
    def _normalizar_caso(caso):
        caso = str(caso).strip()

        if not re.fullmatch(r"\d+", caso):
            raise ValueError("O número do caso deve conter somente dígitos.")

        numero = int(caso)

        if numero <= 0:
            raise ValueError("O número do caso deve ser maior que zero.")

        return f"{numero:02d}"

    def _localizar_diretorio_caso(self, base_dir):
        prefixo = f"caso-{self.caso}"
        diretorios = sorted(
            caminho
            for caminho in base_dir.iterdir()
            if caminho.is_dir() and caminho.name.startswith(prefixo)
        )

        if not diretorios:
            raise FileNotFoundError(
                f"Nenhum diretório encontrado para o caso {self.caso}: {prefixo}*"
            )

        if len(diretorios) > 1:
            nomes = ", ".join(caminho.name for caminho in diretorios)
            raise RuntimeError(
                f"Mais de um diretório encontrado para o caso {self.caso}: {nomes}"
            )

        return diretorios[0]

    def _carregar_fatos(self):
        with self.fatos_path.open("r", encoding="utf-8") as file:
            dados = json.load(file)

        if not dados:
            raise ValueError("O arquivo de fatos está vazio.")

        if (
            isinstance(dados, dict)
            and "aprendizado" in dados
            and "testes" in dados
        ):
            aprendizados = []

            for item in dados["aprendizado"]:
                if isinstance(item, str):
                    aprendizados.append([item])
                    continue

                if isinstance(item, list) and item:
                    if not all(isinstance(fato, str) and fato.strip() for fato in item):
                        raise ValueError(
                            "Cada sequência de aprendizado deve conter somente strings."
                        )

                    aprendizados.append(item)
                    continue

                raise ValueError(
                    "O campo 'aprendizado' deve conter strings ou listas de strings."
                )

            testes = dados["testes"]

            if not isinstance(testes, dict) or not testes:
                raise ValueError(
                    "O campo 'testes' deve ser um objeto no formato {pergunta: fato}."
                )

            return aprendizados, testes

        # Formato antigo:
        #
        # {
        #   "pergunta": "fato"
        # }
        if isinstance(dados, dict):
            return [[fato] for fato in dados.values()], dados

        raise ValueError(
            "O JSON deve ser um objeto no formato {pergunta: fato} "
            "ou conter 'aprendizado' e 'testes'."
        )

    def _print(self, texto=""):
        print(texto)
        self.log_file.write(str(texto) + "\n")
        self.log_file.flush()

    def _progresso(self, prefixo, atual, total):
        restantes = total - atual
        texto = f"{prefixo}: {atual}/{total} | restantes: {restantes}"
        print(f"\r{texto:<100}", end="", flush=True)

    def _limpar_progresso(self):
        print("\r" + (" " * 110) + "\r", end="", flush=True)

    def _erro(self, titulo, exc):
        texto = (
            f"{titulo}\n"
            f"  exceção: {repr(exc)}\n"
            f"{traceback.format_exc()}"
        )

        print("\n" + texto, end="")
        self.log_file.write(texto)
        self.log_file.flush()

    @staticmethod
    def _identificar_consulta(pergunta):
        entidade_match = re.search(
            r"\b(Objeto|Projeto|Pessoa|Servidor)-\d+\b",
            pergunta,
            flags=re.IGNORECASE
        )

        if not entidade_match:
            return None, None

        entidade = entidade_match.group(0)
        pergunta_normalizada = pergunta.lower()

        if "cor" in pergunta_normalizada:
            predicate = "cor"
        elif "tecnologia" in pergunta_normalizada:
            predicate = "tecnologia"
        elif "anos" in pergunta_normalizada or "idade" in pergunta_normalizada:
            predicate = "idade"
        elif "porta" in pergunta_normalizada:
            predicate = "porta"
        else:
            predicate = None

        return entidade, predicate

    @staticmethod
    def _extrair_valor_esperado(fato, predicate):
        if not fato or not predicate:
            return None

        if predicate == "cor":
            matches = re.findall(
                r"\bé\s+([A-Za-zÀ-ÿ-]+)",
                fato,
                flags=re.IGNORECASE
            )

        elif predicate == "tecnologia":
            matches = re.findall(
                r"\busa\s+([A-Za-z0-9+#.+-]+)",
                fato,
                flags=re.IGNORECASE
            )

        elif predicate == "idade":
            matches = re.findall(
                r"\btem\s+(\d+)\s+anos\b",
                fato,
                flags=re.IGNORECASE
            )

        elif predicate == "porta":
            matches = re.findall(
                r"\bporta\s+(\d+)\b",
                fato,
                flags=re.IGNORECASE
            )

        else:
            return None

        if not matches:
            return None

        return matches[-1].strip(" .,;:!?").lower()

    @staticmethod
    def _normalizar_texto(texto):
        if texto is None:
            return ""

        texto = str(texto).lower()
        texto = texto.replace("–", "-").replace("—", "-")
        return texto.strip(" .,;:!?")

    @staticmethod
    def _predicates_compativeis(predicate):
        if predicate == "tecnologia":
            return {
                "tecnologia",
                "linguagem",
                "tecnologia_usada",
                "usa"
            }

        return {predicate}

    def _avaliar(self, pergunta, fato_esperado, resposta):
        prompt = f"""
Você é o avaliador de um teste de memória de um agente de IA.

Analise a PERGUNTA, o FATO ESPERADO e a RESPOSTA.

PERGUNTA:
{pergunta}

FATO ESPERADO:
{fato_esperado}

RESPOSTA:
{resposta}

Classifique a resposta em exatamente uma categoria:

CERTO
Use quando a resposta responde corretamente à informação solicitada pela pergunta.

PARCIAL
Use somente quando a informação solicitada pela pergunta foi respondida corretamente,
porém o fato esperado possui uma informação adicional relevante que não foi informada.

ERRADO
Use quando a informação solicitada não foi respondida corretamente,
quando a resposta diz que não possui a informação, quando contradiz o fato esperado,
quando responde sobre outra entidade ou quando fornece uma informação errada.

REGRAS:

1. Não considere erro de redação uma falha.
2. Se a pergunta pede somente a idade e a resposta informa corretamente a idade,
   mas o fato também possui outra informação relevante, use PARCIAL.
3. Se a pergunta pede somente uma informação e essa informação foi respondida corretamente,
   não use PARCIAL apenas porque outras informações não foram repetidas.
4. "Não sei", "não tenho informação" ou equivalente quando deveria saber = ERRADO.
5. Não invente informações.

Retorne SOMENTE um JSON válido:

{{"classificacao": "CERTO"}}

ou

{{"classificacao": "PARCIAL"}}

ou

{{"classificacao": "ERRADO"}}
"""

        try:
            response = self.atlas.client.chat.completions.create(
                model=self.evaluator_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um avaliador objetivo e rigoroso de respostas."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                reasoning_effort="low",
                response_format={"type": "json_object"}
            )

            content = (response.choices[0].message.content or "").strip()

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                inicio = content.find("{")
                fim = content.rfind("}")

                if inicio == -1 or fim == -1:
                    raise ValueError(
                        f"Resposta do avaliador não é JSON: {content!r}"
                    )

                data = json.loads(content[inicio:fim + 1])

            classificacao = str(
                data.get("classificacao", "")
            ).strip().upper()

            if classificacao not in {"CERTO", "PARCIAL", "ERRADO"}:
                raise ValueError(
                    f"Classificação inválida do avaliador: {classificacao!r}"
                )

            return classificacao

        except Exception as exc:
            self._print(f"  [AVALIADOR] erro: {repr(exc)}")
            return None

    def _validar_no_banco(self, pergunta, fato_esperado):
        entidade_nome, predicate = self._identificar_consulta(pergunta)

        resultado = {
            "entidade": entidade_nome,
            "predicate": predicate,
            "valor_esperado": None,
            "entity_existe": False,
            "predicate_existe": False,
            "valor_esperado_existe": False,
            "valores_encontrados": []
        }

        if not entidade_nome:
            return resultado

        entity_id = self.atlas.memory.find_entity_id(entidade_nome)

        if entity_id is None:
            return resultado

        resultado["entity_existe"] = True
        resultado["valor_esperado"] = self._extrair_valor_esperado(
            fato_esperado,
            predicate
        )

        predicates_validos = self._predicates_compativeis(predicate)

        memorias = self.atlas.memory.get_current_memories(
            entity_id=entity_id,
            limit=100
        )

        for memoria in memorias:
            memoria_predicate = str(
                memoria.get("predicate", "")
            ).strip().lower()

            if memoria_predicate not in predicates_validos:
                continue

            resultado["predicate_existe"] = True

            valor = memoria.get("value")
            resultado["valores_encontrados"].append(valor)

            if resultado["valor_esperado"] is None:
                continue

            if (
                self._normalizar_texto(valor)
                == self._normalizar_texto(resultado["valor_esperado"])
            ):
                resultado["valor_esperado_existe"] = True

        # Tecnologia também pode estar armazenada como relação:
        # Projeto -> usa -> PostgreSQL
        if predicate == "tecnologia":
            try:
                relacoes = self.atlas.memory.get_related_relations(
                    entity_id=entity_id,
                    direction="subject",
                    limit=100
                )
            except Exception as exc:
                relacoes = []
                self._print(
                    f"  [BANCO] erro consultando relações: {repr(exc)}"
                )

            for relacao in relacoes:
                relacao_predicate = str(
                    relacao.get("predicate", "")
                ).strip().lower()

                if relacao_predicate not in {
                    "usa",
                    "utiliza",
                    "tecnologia"
                }:
                    continue

                resultado["predicate_existe"] = True

                valor = relacao.get("object")
                resultado["valores_encontrados"].append(valor)

                if resultado["valor_esperado"] is None:
                    continue

                if (
                    self._normalizar_texto(valor)
                    == self._normalizar_texto(
                        resultado["valor_esperado"]
                    )
                ):
                    resultado["valor_esperado_existe"] = True

        return resultado

    def _imprimir_validacao_banco(self, validacao):
        self._print("  [BANCO]")
        self._print(f"    entidade              : {validacao.get('entidade')}")
        self._print(
            f"    entity_existe         : "
            f"{'SIM' if validacao.get('entity_existe') else 'NÃO'}"
        )
        self._print(f"    predicate             : {validacao.get('predicate')}")
        self._print(
            f"    predicate_existe      : "
            f"{'SIM' if validacao.get('predicate_existe') else 'NÃO'}"
        )
        self._print(
            f"    valor_esperado        : {validacao.get('valor_esperado')}"
        )
        self._print(
            f"    valor_esperado_existe : "
            f"{'SIM' if validacao.get('valor_esperado_existe') else 'NÃO'}"
        )
        self._print(
            f"    valores_encontrados   : "
            f"{validacao.get('valores_encontrados')}"
        )

    def _ensinar_fato(self, fato):
        message_id = self.atlas.memory.save_message(
            self.learning_conversation_id,
            "user",
            fato
        )

        extracted = self.atlas.extractor.extract(fato, [])
        self.atlas.persister.persist(extracted, message_id)

    def _testar_pergunta(self, pergunta):
        return self.atlas.process_message(
            self.test_conversation_id,
            pergunta
        )

    def ensinar_todos_os_fatos(self):
        fatos = [
            fato
            for sequencia in self.aprendizados
            for fato in sequencia
        ]

        total = len(fatos)
        inicio = time.perf_counter()
        registrados = 0
        erros = 0
        indice = 0

        for sequencia in self.aprendizados:
            for fato in sequencia:
                indice += 1

                try:
                    self._ensinar_fato(fato)
                    registrados += 1

                except Exception as exc:
                    erros += 1
                    self._limpar_progresso()
                    self._erro(
                        f"[ERRO AO ENSINAR] {fato}",
                        exc
                    )
                    print()

                self._progresso("Aprendizado", indice, total)

        self._limpar_progresso()

        duracao = time.perf_counter() - inicio

        self._print(
            f"Aprendizado concluído: {registrados}/{total} fatos "
            f"em {duracao:.2f}s."
        )
        self._print(f"Erros no aprendizado: {erros}")
        self._print("")

    def testar_todos_os_fatos(self):
        itens = list(self.testes.items())
        random.shuffle(itens)

        total = len(itens)
        inicio = time.perf_counter()

        certos = 0
        parciais = 0
        errados = 0
        falhas_avaliador = 0
        falhas_execucao = 0

        errados_entidade_ausente = 0
        errados_predicate_ausente = 0
        errados_valor_ausente = 0
        errados_valor_presente = 0

        parciais_entidade_ausente = 0
        parciais_predicate_ausente = 0
        parciais_valor_ausente = 0
        parciais_valor_presente = 0

        for indice, (pergunta, fato) in enumerate(itens, start=1):
            try:
                resposta = self._testar_pergunta(pergunta)
                classificacao = self._avaliar(
                    pergunta,
                    fato,
                    resposta
                )

                if classificacao is None:
                    falhas_avaliador += 1
                    self._limpar_progresso()
                    self._print(f"[AVALIADOR] {pergunta}")
                    self._print(f"  esperado : {fato}")
                    self._print(f"  resposta : {resposta}")
                    self._print("")

                elif classificacao == "CERTO":
                    certos += 1

                else:
                    validacao = self._validar_no_banco(
                        pergunta,
                        fato
                    )

                    if classificacao == "PARCIAL":
                        parciais += 1

                        if not validacao["entity_existe"]:
                            parciais_entidade_ausente += 1
                        elif not validacao["predicate_existe"]:
                            parciais_predicate_ausente += 1
                        elif validacao["valor_esperado_existe"]:
                            parciais_valor_presente += 1
                        else:
                            parciais_valor_ausente += 1

                    else:
                        errados += 1

                        if not validacao["entity_existe"]:
                            errados_entidade_ausente += 1
                        elif not validacao["predicate_existe"]:
                            errados_predicate_ausente += 1
                        elif validacao["valor_esperado_existe"]:
                            errados_valor_presente += 1
                        else:
                            errados_valor_ausente += 1

                    self._limpar_progresso()
                    self._print(f"[{classificacao}] {pergunta}")
                    self._print(f"  esperado : {fato}")
                    self._print(f"  resposta : {resposta}")
                    self._imprimir_validacao_banco(validacao)
                    self._print("")

            except Exception as exc:
                errados += 1
                falhas_execucao += 1
                self._limpar_progresso()
                self._erro(f"[ERRO EXECUÇÃO] {pergunta}", exc)
                self._print("")

            self._progresso(
                "Teste",
                indice,
                total
            )

        self._limpar_progresso()

        total_avaliados = certos + parciais + errados
        duracao = time.perf_counter() - inicio

        percentual_certos = (
            certos / total_avaliados * 100
            if total_avaliados
            else 0
        )
        percentual_parciais = (
            parciais / total_avaliados * 100
            if total_avaliados
            else 0
        )
        percentual_errados = (
            errados / total_avaliados * 100
            if total_avaliados
            else 0
        )

        self._print("=" * 70)
        self._print("RESULTADO FINAL")
        self._print("=" * 70)
        self._print(f"Total              : {total}")
        self._print(f"Avaliados          : {total_avaliados}")
        self._print(f"CERTOS             : {certos}")
        self._print(f"PARCIAIS           : {parciais}")
        self._print(f"ERRADOS            : {errados}")
        self._print(f"Falhas avaliador   : {falhas_avaliador}")
        self._print(f"Falhas execução    : {falhas_execucao}")
        self._print("")
        self._print(f"% CERTOS           : {percentual_certos:.2f}%")
        self._print(f"% PARCIAIS         : {percentual_parciais:.2f}%")
        self._print(f"% ERRADOS          : {percentual_errados:.2f}%")
        self._print("")

        self._print("ANÁLISE DOS ERRADOS NO BANCO")
        self._print(f"  Entidade ausente : {errados_entidade_ausente}")
        self._print(f"  Predicate ausente: {errados_predicate_ausente}")
        self._print(f"  Valor ausente    : {errados_valor_ausente}")
        self._print(f"  Valor presente   : {errados_valor_presente}")
        self._print("")

        self._print("ANÁLISE DOS PARCIAIS NO BANCO")
        self._print(f"  Entidade ausente : {parciais_entidade_ausente}")
        self._print(f"  Predicate ausente: {parciais_predicate_ausente}")
        self._print(f"  Valor ausente    : {parciais_valor_ausente}")
        self._print(f"  Valor presente   : {parciais_valor_presente}")
        self._print("")

        conhecimento_ausente = (
            errados_entidade_ausente
            + errados_predicate_ausente
            + errados_valor_ausente
        )

        self._print("INTERPRETAÇÃO DOS ERRADOS")
        self._print(
            f"  Conhecimento não encontrado no banco: "
            f"{conhecimento_ausente}"
        )
        self._print(
            f"  Conhecimento presente no banco       : "
            f"{errados_valor_presente}"
        )
        self._print("")
        self._print(f"Tempo teste       : {duracao:.2f}s")
        self._print("=" * 70)

    def executar(self):
        total_aprendizado = sum(
            len(sequencia)
            for sequencia in self.aprendizados
        )
        total_testes = len(self.testes)

        if total_aprendizado < 1:
            raise ValueError("É necessário ter pelo menos 1 fato para aprendizado.")

        if total_testes < 1:
            raise ValueError("É necessário ter pelo menos 1 teste.")

        try:
            self._print("=" * 70)
            self._print("TESTER - ATLAS")
            self._print(f"Caso                : {self.caso}")
            self._print(f"Diretório            : {self.caso_dir}")
            self._print(f"Fatos aprendizado    : {total_aprendizado}")
            self._print(f"Testes               : {total_testes}")
            self._print(f"Avaliador            : {self.evaluator_model}")
            self._print(f"Log                  : {self.log_path}")
            self._print("=" * 70)
            self._print("")

            self.ensinar_todos_os_fatos()
            self.testar_todos_os_fatos()

        except Exception as exc:
            self._limpar_progresso()
            self._erro("[ERRO FATAL] Execução do tester", exc)
            raise

        finally:
            self.log_file.flush()
            self.log_file.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python tester.py <numero_do_caso>\n"
            "Exemplo: python tester.py 01"
        )

    Tester(sys.argv[1]).executar()