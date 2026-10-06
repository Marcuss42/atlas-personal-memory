def build_prompt(message, context):
    return f"""
Extraia SOMENTE conhecimento persistente sustentado pela MENSAGEM ATUAL.

O CONTEXTO existe somente para resolver referências da mensagem atual.
Nunca copie conhecimento antigo do contexto.

RETORNE SOMENTE JSON VÁLIDO:

{{
  "entities": [],
  "memories": [],
  "relations": [],
  "instructions": []
}}

REGRAS

1. Não invente fatos, entidades ou relações.
2. "self" representa o usuário e nunca aparece em "entities".
3. Pronomes não são entidades.
4. Uma entidade representa um REFERENCIAL INDEPENDENTE.
5. Não crie uma entidade só porque uma palavra ou valor apareceu na frase.
6. Valores literais, números, datas, quantidades, configurações e atributos
   devem normalmente ficar em "memories".
7. Um conceito nomeado pode ser entidade quando funciona como referencial
   independente em uma relação.
8. Não transforme automaticamente todo valor em entidade.
9. Use "relations" somente quando a afirmação conecta DOIS REFERENCIAIS
   INDEPENDENTES.
10. Use "memories" para atributos, propriedades, configurações e fatos que
    possuem um valor.
11. Números, portas, idades, preços, códigos, datas e outros valores literais
    NÃO são entidades por padrão.
12. A mesma afirmação não deve aparecer simultaneamente nas duas estruturas.
13. Só extraia conhecimento da mensagem atual.
14. Use o contexto somente para resolver referências.
15. Toda referência usada deve existir em "entities", exceto "self".
16. Não crie entidades artificiais como "porta_4102", "idade_20" ou
    "preco_100".
17. Não force classificação por tipo. O sistema deve ser genérico.
18. Uma atualização ou correção deve produzir somente o NOVO valor ou NOVA
    relação.
19. Quando uma memória substituir explicitamente um valor anterior, informe
    "resolution": "correction".
20. Quando uma memória representar uma atualização de valor sem uma correção
    explícita, informe "resolution": "update".
21. Quando uma relation substituir explicitamente uma relation anterior,
    informe "resolution": "correction".
22. Quando uma relation representar uma atualização sem uma correção
    explícita, informe "resolution": "update".
23. Para memories novas, sem atualização ou correção, use
    "resolution": null.
24. Para relations novas, sem atualização ou correção, use
    "resolution": null.
25. "resolution" é um campo válido tanto em "memories" quanto em "relations".
26. Nunca omita "resolution" de uma memory ou relation.
27. Retorne exatamente quatro chaves no objeto raiz:
    entities, memories, relations e instructions.

COMO USAR RESOLUTION

Cada objeto em "memories" deve possuir:

"resolution": null

ou:

"resolution": "update"

ou:

"resolution": "correction"

Cada objeto em "relations" deve possuir:

"resolution": null

ou:

"resolution": "update"

ou:

"resolution": "correction"

Use "correction" quando a mensagem indicar explicitamente que o valor ou
relação anterior foi substituído, estava incorreto ou deixou de ser válido.

Use "update" quando a mensagem indicar uma mudança sem declarar
explicitamente uma correção.

MEMORY CORRECTION

Exemplo:

"Objeto-001 era azul, mas agora é vermelho."

Retorne somente o NOVO valor:

{{
  "subject_ref": "objeto_001",
  "kind": "fact",
  "predicate": "cor",
  "value": "vermelho",
  "value_type": "text",
  "importance": 0.8,
  "confidence": 0.99,
  "search_terms": ["cor", "vermelho"],
  "resolution": "correction"
}}

NÃO retorne "azul" como outra memória.

Outro exemplo:

"Servidor-002 usava a porta 4002, mas agora usa a porta 4202."

Retorne:

{{
  "subject_ref": "servidor_002",
  "kind": "fact",
  "predicate": "porta",
  "value": "4202",
  "value_type": "number",
  "importance": 0.8,
  "confidence": 0.99,
  "search_terms": ["porta", "4202"],
  "resolution": "correction"
}}

Outro exemplo:

"Pessoa-004 tinha 28 anos, mas agora tem 29 anos."

Retorne:

{{
  "subject_ref": "pessoa_004",
  "kind": "fact",
  "predicate": "idade",
  "value": "29",
  "value_type": "number",
  "importance": 0.8,
  "confidence": 0.99,
  "search_terms": ["idade", "29"],
  "resolution": "correction"
}}

Outro exemplo:

"Projeto-003 usava Java, mas agora usa Python."

Retorne:

{{
  "subject_ref": "projeto_003",
  "kind": "fact",
  "predicate": "tecnologia",
  "value": "Python",
  "value_type": "text",
  "importance": 0.8,
  "confidence": 0.99,
  "search_terms": ["tecnologia", "Python"],
  "resolution": "correction"
}}

RELATION CORRECTION

Quando a mensagem substituir uma relação anterior entre o mesmo sujeito
e predicado por outro objeto, represente a NOVA relação em "relations".

Exemplo:

"Projeto-005 usava Redis, mas agora usa PostgreSQL."

"Projeto-005" e "PostgreSQL" são referenciais independentes nomeados.

Retorne:

{{
  "entities": [
    {{
      "ref": "projeto_005",
      "name": "Projeto-005",
      "type": "projeto",
      "aliases": []
    }},
    {{
      "ref": "postgresql",
      "name": "PostgreSQL",
      "type": "tecnologia",
      "aliases": []
    }}
  ],
  "memories": [],
  "relations": [
    {{
      "subject_ref": "projeto_005",
      "predicate": "usa",
      "object_ref": "postgresql",
      "symmetric": false,
      "confidence": 0.99,
      "resolution": "correction"
    }}
  ],
  "instructions": []
}}

NÃO crie uma memory como:

"predicate": "tecnologia",
"value": "PostgreSQL"

quando a afirmação estabelece uma relação entre dois referenciais
independentes.

NÃO retorne a relação antiga com Redis.

RELATION UPDATE

Exemplo:

"Projeto-005 agora usa PostgreSQL."

Retorne:

{{
  "entities": [
    {{
      "ref": "projeto_005",
      "name": "Projeto-005",
      "type": "projeto",
      "aliases": []
    }},
    {{
      "ref": "postgresql",
      "name": "PostgreSQL",
      "type": "tecnologia",
      "aliases": []
    }}
  ],
  "memories": [],
  "relations": [
    {{
      "subject_ref": "projeto_005",
      "predicate": "usa",
      "object_ref": "postgresql",
      "symmetric": false,
      "confidence": 0.99,
      "resolution": "update"
    }}
  ],
  "instructions": []
}}

COMO DIFERENCIAR MEMORY DE RELATION

Use "memories" quando a frase informa uma propriedade, atributo,
configuração ou valor pertencente a uma entidade.

Use "relations" quando a frase estabelece uma relação entre duas entidades
ou referenciais independentes.

A palavra "usa", "tem", "possui", "fica em" ou qualquer outro verbo
NÃO determina sozinha que deve ser usada uma relation.
Observe o papel semântico do objeto.

Exemplo:

"O Servidor-001 usa a porta 4101."

"Servidor-001" é uma entidade.
"4101" é um valor literal de configuração.
"porta" é o atributo.

Portanto, isso é uma MEMORY, e NÃO uma relation:

{{
  "entities": [
    {{
      "ref": "servidor_001",
      "name": "Servidor-001",
      "type": "unknown",
      "aliases": []
    }}
  ],
  "memories": [
    {{
      "subject_ref": "servidor_001",
      "kind": "fact",
      "predicate": "porta",
      "value": "4101",
      "value_type": "number",
      "importance": 0.8,
      "confidence": 0.99,
      "search_terms": ["porta", "4101"],
      "resolution": null
    }}
  ],
  "relations": [],
  "instructions": []
}}

Mesmo que o verbo seja "usa", "utiliza", "possui", "tem" ou equivalente,
se o objeto for um valor literal ou atributo, represente como "memory".

Exemplos que devem ser MEMORY:

"Servidor-002 usa a porta 4102."
→ predicate = "porta"
→ value = "4102"
→ resolution = null

"Pessoa-003 tem 41 anos."
→ predicate = "idade"
→ value = "41"
→ resolution = null

"Produto-010 custa 99 reais."
→ predicate = "preco"
→ value = "99"
→ resolution = null

"Equipamento-005 opera em 220 volts."
→ predicate = "tensao"
→ value = "220"
→ resolution = null

Exemplos que devem ser RELATION:

"Projeto A usa SQLite."
→ Projeto A e SQLite são referenciais independentes.

"Lucas e Matheus são amigos."
→ Lucas e Matheus são referenciais independentes.

"Alice trabalha para a Empresa X."
→ Alice e Empresa X são referenciais independentes.

IDENTIDADE

"Eu sou Marcus"

{{
  "entities": [],
  "memories": [
    {{
      "subject_ref": "self",
      "kind": "fact",
      "predicate": "nome",
      "value": "Marcus",
      "value_type": "text",
      "importance": 0.9,
      "confidence": 1.0,
      "search_terms": ["nome", "Marcus"],
      "resolution": null
    }}
  ],
  "relations": [],
  "instructions": []
}}

RELAÇÃO

"Lucas e Matheus são amigos"

{{
  "entities": [
    {{
      "ref": "lucas",
      "name": "Lucas",
      "type": "pessoa",
      "aliases": []
    }},
    {{
      "ref": "matheus",
      "name": "Matheus",
      "type": "pessoa",
      "aliases": []
    }}
  ],
  "memories": [],
  "relations": [
    {{
      "subject_ref": "lucas",
      "predicate": "amigo",
      "object_ref": "matheus",
      "symmetric": true,
      "confidence": 0.99,
      "resolution": null
    }}
  ],
  "instructions": []
}}

PRIMEIRA PESSOA

"Eu tenho um amigo chamado Lucas"

{{
  "entities": [
    {{
      "ref": "lucas",
      "name": "Lucas",
      "type": "pessoa",
      "aliases": []
    }}
  ],
  "memories": [],
  "relations": [
    {{
      "subject_ref": "self",
      "predicate": "amigo",
      "object_ref": "lucas",
      "symmetric": true,
      "confidence": 0.99,
      "resolution": null
    }}
  ],
  "instructions": []
}}

RELAÇÃO DIRECIONAL

"Projeto A usa SQLite"

Essa afirmação é uma relation porque "Projeto A" e "SQLite" são
referenciais nomeados independentes:

{{
  "entities": [
    {{
      "ref": "projeto_a",
      "name": "Projeto A",
      "type": "projeto",
      "aliases": []
    }},
    {{
      "ref": "sqlite",
      "name": "SQLite",
      "type": "tecnologia",
      "aliases": []
    }}
  ],
  "memories": [],
  "relations": [
    {{
      "subject_ref": "projeto_a",
      "predicate": "usa",
      "object_ref": "sqlite",
      "symmetric": false,
      "confidence": 0.99,
      "resolution": null
    }}
  ],
  "instructions": []
}}

Importante:

"Projeto A usa SQLite."
→ relation, porque SQLite é um referencial nomeado.

"Servidor-001 usa a porta 4101."
→ memory, porque 4101 é um valor de configuração e "porta"
   é um atributo do servidor.

Não transforme qualquer palavra que seja um valor em entidade.
Considere sempre o papel semântico do conceito na afirmação.

MEMÓRIA

"Matheus tem 20 anos"

{{
  "entities": [
    {{
      "ref": "matheus",
      "name": "Matheus",
      "type": "pessoa",
      "aliases": []
    }}
  ],
  "memories": [
    {{
      "subject_ref": "matheus",
      "kind": "fact",
      "predicate": "idade",
      "value": "20",
      "value_type": "number",
      "importance": 0.8,
      "confidence": 0.99,
      "search_terms": ["idade", "20 anos"],
      "resolution": null
    }}
  ],
  "relations": [],
  "instructions": []
}}

CONFIGURAÇÃO

"Servidor-001 usa a porta 4101"

{{
  "entities": [
    {{
      "ref": "servidor_001",
      "name": "Servidor-001",
      "type": "unknown",
      "aliases": []
    }}
  ],
  "memories": [
    {{
      "subject_ref": "servidor_001",
      "kind": "fact",
      "predicate": "porta",
      "value": "4101",
      "value_type": "number",
      "importance": 0.8,
      "confidence": 0.99,
      "search_terms": ["porta", "4101"],
      "resolution": null
    }}
  ],
  "relations": [],
  "instructions": []
}}

REFERÊNCIA

Contexto:
"Matheus tem 20 anos."

Mensagem:
"Ele tem 5 gatos."

Resolva "Ele" como Matheus.

Não crie automaticamente uma entidade "gatos".

ATUALIZAÇÃO

Contexto:
"Matheus tem 20 anos."

Mensagem:
"Matheus tem 21 anos."

Extraia somente o novo valor.

{{
  "entities": [
    {{
      "ref": "matheus",
      "name": "Matheus",
      "type": "pessoa",
      "aliases": []
    }}
  ],
  "memories": [
    {{
      "subject_ref": "matheus",
      "kind": "fact",
      "predicate": "idade",
      "value": "21",
      "value_type": "number",
      "importance": 0.8,
      "confidence": 0.99,
      "search_terms": ["idade", "21"],
      "resolution": "update"
    }}
  ],
  "relations": [],
  "instructions": []
}}

Não repita o valor 20.

CORREÇÃO

Contexto:
"Matheus tem 20 anos."

Mensagem:
"Matheus tinha 20 anos, mas agora tem 21 anos."

Extraia somente o novo valor.

{{
  "entities": [
    {{
      "ref": "matheus",
      "name": "Matheus",
      "type": "pessoa",
      "aliases": []
    }}
  ],
  "memories": [
    {{
      "subject_ref": "matheus",
      "kind": "fact",
      "predicate": "idade",
      "value": "21",
      "value_type": "number",
      "importance": 0.8,
      "confidence": 0.99,
      "search_terms": ["idade", "21"],
      "resolution": "correction"
    }}
  ],
  "relations": [],
  "instructions": []
}}

Não extraia o valor antigo como memória atual.

ALIAS

"Lucas também é conhecido como Lu"

Use Lucas como entidade e coloque "Lu" em aliases.

Não copie fatos antigos do contexto.

INSTRUÇÕES

Instruções persistentes do usuário ficam em "instructions":

{{
  "content": "...",
  "importance": 0.9
}}

NÃO EXTRAIA

- perguntas;
- saudações;
- conversas triviais;
- hipóteses;
- especulações;
- conhecimento geral sem valor persistente;
- entidades não necessárias;
- fatos antigos não sustentados pela mensagem atual.

CONTEXTO RECENTE

{context}

MENSAGEM ATUAL

{message}
""".strip()