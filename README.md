# Atlas — Personal Memory Agent

Um agente de IA em Python com memória persistente de longo prazo, criado para armazenar, organizar, recuperar e atualizar conhecimento ao longo das conversas.

O objetivo do Atlas não é colocar todo o histórico no prompt. A proposta é manter um sistema externo de memória capaz de localizar as informações relevantes para cada pergunta e fornecer esse conhecimento ao LLM quando necessário.

> **Status:** projeto em desenvolvimento. A base de memória persistente já funciona, mas vários componentes descritos neste documento ainda estão em implementação ou planejamento.

## Objetivo

O Atlas foi projetado para funcionar como um assistente pessoal com memória persistente e genérica.

Ele não depende de categorias fixas de conhecimento. A ideia é permitir que o agente memorize informações pessoais, projetos, códigos, servidores, configurações, ideias, preferências, decisões e outros conhecimentos relevantes.

O princípio central é:

**O LLM interpreta as informações; o sistema de memória armazena e recupera os dados de forma persistente.**

## O que já existe

### Memória persistente

As mensagens das conversas são armazenadas de forma persistente, mantendo seu conteúdo original para que o conhecimento não dependa apenas da interpretação feita pelo LLM.

### Memória de curto prazo

O agente utiliza uma janela de mensagens recentes para manter continuidade na conversa e interpretar referências como "ele", "isso" ou "aquele projeto".

### Memória estruturada

O sistema já possui armazenamento estruturado para informações extraídas das conversas, incluindo fatos e relações entre entidades.

### Entidades e relações

O banco possui entidades estáveis e relações entre entidades. As relações são armazenadas de forma independente das mensagens originais.

### Atualizações e histórico

Correções de informações já são tratadas pelo sistema. Quando um valor é atualizado, o valor anterior pode permanecer como histórico enquanto o novo valor passa a ser o atual.

Isso já foi validado em testes envolvendo valores simples e relações, por exemplo:

- uma cor que mudou de azul para vermelho;
- uma porta que mudou de 4002 para 4202;
- uma tecnologia que mudou de Java para Python;
- uma relação que mudou de Redis para PostgreSQL.

### Busca textual

A recuperação já utiliza SQLite e SQLite FTS5 para localizar informações armazenadas.

### Roteamento de consultas

Existe um Query Router responsável por interpretar a intenção da pergunta e montar um plano de consulta antes da recuperação da memória.

Essa camada já está funcionando, mas ainda possui casos de interpretação incorreta em consultas relacionadas a entidades e relações.

### Extração de conhecimento

A extração de fatos, entidades e relações é realizada por um LLM dedicado, separado do modelo utilizado para responder ao usuário.

### Testes automatizados do agente

O projeto possui um sistema de testes por casos para ensinar fatos, executar perguntas e validar os resultados diretamente contra a memória armazenada.

## Em desenvolvimento

As partes abaixo já fazem parte da arquitetura atual ou estão sendo refinadas, mas ainda não devem ser consideradas concluídas.

### Query Router

O roteador ainda precisa melhorar a interpretação semântica de determinados tipos de pergunta.

Exemplo:

> Qual tecnologia o Projeto-003 usa atualmente?

Uma consulta desse tipo ainda pode ser transformada em um plano incorreto, dificultando a recuperação direta da relação correta.

O mesmo ocorre em consultas inversas como:

> Qual servidor usa a porta 6811?

Nos testes atuais, a resposta pode ser encontrada por fallback usando FTS, mesmo quando o plano semântico gerado pelo router não representa corretamente a consulta.

### Aliases de entidades

A estrutura de entidades e aliases faz parte do modelo de dados, porém o reconhecimento, associação e correção automática de aliases ainda precisam ser amadurecidos.

### Instruções persistentes

O projeto prevê um mecanismo específico para armazenar instruções comportamentais permanentes, como preferências de formato, tom e regras de resposta.

Essa funcionalidade ainda está em desenvolvimento.

### Contexto de origem das memórias

A arquitetura prevê referências das memórias às mensagens que deram origem aos registros, permitindo recuperar posteriormente o contexto original.

A estrutura de persistência está sendo evoluída para tornar esse rastreamento mais completo e consistente.

## Planejado

Os itens abaixo fazem parte da visão do projeto, mas ainda não estão implementados como parte da primeira versão funcional.

### Busca semântica

Adicionar embeddings e um índice vetorial para complementar a busca textual, utilizando semântica quando a correspondência por termos não for suficiente.

### Busca híbrida

Combinar de forma mais sofisticada:

- busca exata;
- palavras-chave;
- SQLite FTS5;
- entidades e aliases;
- relações;
- busca semântica;
- histórico original.

A recuperação deverá dar peso aos termos explícitos da pergunta e ao contexto das entidades envolvidas.

### Resolução de contradições ambíguas

Quando uma nova informação entrar em conflito com uma informação antiga sem indicar claramente uma correção, o agente deverá ser capaz de identificar a ambiguidade e perguntar ao usuário qual versão deve permanecer válida.

### Eventos e validade temporal

Adicionar suporte explícito a eventos, validade temporal e consultas históricas, permitindo diferenciar perguntas como:

> Qual é o valor atual?

ou

> Qual valor havia sido informado anteriormente?

### Instruções persistentes completas

Implementar seleção, prioridade, consolidação, substituição e arquivamento de instruções comportamentais sem consumir contexto desnecessariamente.

### Cofre de segredos

Implementar uma camada separada para informações sensíveis, como senhas, tokens, chaves privadas e credenciais.

Os valores deverão permanecer criptografados em repouso e nunca serem tratados como memória comum.

A arquitetura planejada inclui:

- senha do cofre definida pelo usuário;
- derivação de chave com função apropriada, como Argon2id;
- verificação segura da senha;
- proteção da chave utilizada para os segredos;
- criptografia autenticada dos valores, como AES-GCM ou ChaCha20-Poly1305;
- desbloqueio explícito;
- ausência de segredos e chaves reais no código público;
- exclusão dos valores secretos das buscas normais e dos prompts quando não forem necessários.

### Retenção e manutenção da memória

Criar políticas configuráveis para retenção, arquivamento, consolidação e remoção de informações.

O histórico bruto e o conhecimento estruturado deverão poder possuir políticas diferentes.

### Reprocessamento e recuperação de falhas

Permitir que mensagens armazenadas sejam reprocessadas quando a extração ou outra etapa de memória falhar, sem perder o conteúdo original.

### Otimização e escalabilidade

Medir latência, tamanho do banco, custo das chamadas ao LLM, consumo de memória e desempenho da busca antes de adicionar tecnologias externas.

Redis, Elasticsearch/OpenSearch ou outros componentes externos poderão ser considerados somente quando houver necessidade comprovada.

## Arquitetura atual

A primeira versão está sendo construída como uma aplicação Python única, organizada em módulos.

Componentes principais:

1. Gerenciamento de conversas.
2. Armazenamento de mensagens.
3. Extração de conhecimento.
4. Gerenciamento de entidades e relações.
5. Atualização e histórico de memórias.
6. Busca e recuperação.
7. Query Router.
8. Montagem de contexto e prompt.
9. Testes de memória e recuperação.

Componentes como cofre de segredos, manutenção avançada e recuperação semântica continuam planejados.

## Tecnologias

- **Python** — linguagem principal.
- **SQLite** — armazenamento persistente.
- **SQLite FTS5** — busca textual.
- **LLM via OpenRouter** — extração e interpretação.
- **Criptografia** — planejada para a camada de segredos.
- **Embeddings / índice vetorial** — planejados para recuperação semântica.

A arquitetura foi pensada para não depender de um provedor ou modelo específico de IA.

## Modelo de dados

A estrutura atual já utiliza tabelas para representar elementos fundamentais da memória, incluindo:

- `conversations`
- `messages`
- `entities`
- `entity_aliases`
- `memory_items`
- `relations`
- `memory_versions`
- `memory_links`
- `instructions`
- índices e estruturas auxiliares de busca

Algumas estruturas previstas no projeto, como `events` e `secrets`, ainda fazem parte da evolução planejada.

O esquema não é considerado definitivo.

## Princípios

- Todas as mensagens originais devem ser preservadas.
- A memória curta serve para continuidade, não para substituir a memória persistente.
- O conhecimento estruturado deve possuir origem rastreável.
- Atualizações não devem apagar silenciosamente o histórico.
- Entidades devem possuir identificadores estáveis.
- Relações devem ser flexíveis e não depender de uma lista fixa de tipos.
- Contradições ambíguas não devem ser resolvidas por suposição silenciosa.
- A recuperação deve combinar diferentes estratégias.
- O LLM não deve ser a única fonte de verdade da memória.
- O banco deve continuar sendo a fonte persistente dos dados estruturados.
- Falhas do LLM não devem apagar o histórico original.
- Segurança não pode depender de uma chave secreta fixa dentro do código-fonte.

## Roadmap

### Fundação

- [x] Persistência das mensagens.
- [x] Banco SQLite.
- [x] Memória de curto prazo.
- [x] Memória estruturada inicial.
- [x] Entidades e relações.
- [x] Atualizações com histórico.
- [x] Busca textual com FTS5.
- [x] Query Router inicial.
- [x] Testes automatizados da memória.

### Em desenvolvimento

- [ ] Melhorar o Query Router.
- [ ] Refinar consultas por relações.
- [ ] Melhorar aliases e resolução de entidades.
- [ ] Completar rastreamento de origem/contexto das memórias.
- [ ] Implementar instruções persistentes.

### Planejado

- [ ] Busca semântica por embeddings.
- [ ] Recuperação híbrida.
- [ ] Resolução de contradições ambíguas.
- [ ] Eventos e validade temporal.
- [ ] Cofre de segredos criptografado.
- [ ] Retenção e consolidação de memória.
- [ ] Reprocessamento robusto após falhas.
- [ ] Métricas e otimizações de desempenho.
- [ ] Avaliar cache externo e outros componentes somente quando necessários.

## Objetivo final

Construir um assistente pessoal capaz de conversar normalmente, lembrar informações de longo prazo, recuperar conhecimento de conversas antigas, entender aliases, relacionar entidades, manter preferências persistentes e atualizar informações sem perder o histórico original.

A proposta do Atlas é transformar memória em um sistema próprio, persistente e verificável, deixando para o LLM a responsabilidade de interpretar e utilizar as informações relevantes.
