# Fase 4 FAQ e Base de Conhecimento

## Estado

Design da Fase 4 para o trilho da competicao. Esta fase parte da Fase 3 integrada em `main` no commit `01d8d252292b7795f2ae6c94bc5c0144cba13491` e adiciona uma camada dedicada de conhecimento aprovado sem alterar semanticamente o corpus historico nem transformar historicos de tickets em procedimentos oficiais.

Principio central do produto:

> O objetivo nao e automatizar o chamado. E descobrir se o chamado precisa existir.

A entrega conceitual desta fase e separar de forma executavel:

```text
historico real nao validado
        -> candidato de conhecimento
        -> revisao humana
        -> conhecimento APPROVED
        -> retrieval seguro
        -> orientacao literal aprovada
```

A Fase 4 nao implementa promocao automatica de historicos para conhecimento. Historicos podem futuramente ajudar a criar candidatos, mas nunca autorizam orientacao oficial por si mesmos.

## Objetivo

Criar uma base de FAQ e conhecimento com schema proprio, validacao, indexacao e retrieval seguros. Somente artigos `APPROVED` podem ser recuperados como orientacao oficial.

O fluxo minimo deve ser:

```text
texto do usuario
-> classificacao existente de intent/system
-> verificacao de contexto
-> busca somente em conhecimento APPROVED compativel
-> score semantico com threshold 0.65
-> resposta literal do campo answer
```

Se qualquer gate falhar, o sistema se abstem e retorna `NO_APPROVED_KNOWLEDGE`.

## Principios obrigatorios

1. O dominio publico de knowledge usa `knowledge_id`, `title`, `question`, `answer`, `system`, `intent`, `tags`, `source`, `status`, `reviewed_by`, `reviewed_at` e `version`.
2. Nomes e conceitos de ticket usados por `build_index` sao detalhe privado de adaptacao e nunca fazem parte da API publica de knowledge.
3. `build_index` e `load_index` podem ser reutilizados apenas como infraestrutura interna de persistencia vetorial, integridade, checkpoint e provenance do modelo.
4. Somente `APPROVED` entra no indice de conhecimento.
5. `DRAFT` e `RETIRED` nunca podem produzir orientacao oficial.
6. A resposta entregue ao usuario e exatamente o `answer` aprovado. O LLM nao reescreve, resume, completa ou inventa procedimento nesta fase.
7. A classificacao existente e o embedder local homologado podem ser reutilizados.
8. O threshold de runtime permanece `0.65`.
9. Contexto ambiguo, sistema desconhecido, mismatch de sistema, mismatch de intent ou baixa evidencia resultam em abstinencia.
10. FAQ de outro sistema nunca pode ser usada para completar resultados.
11. Nenhum dado corporativo real entra no Git, fixtures ou logs do CI.
12. Fixtures e FAQs versionadas da Fase 4 sao 100% sinteticas.
13. `retrieval.py` e `index.py` homologados nao serao alterados se a camada dedicada puder resolver o requisito.
14. Qualquer necessidade real de alterar uma fundacao das Fases 1 a 3 deve ser tratada como bloqueio concreto antes da mudanca.
15. Provenance de knowledge e obrigatoria e fail-closed. Busca nunca tenta inferir ou reparar provenance ausente ou divergente.

## Reuso obrigatorio

A Fase 4 reutiliza:

- `classify_ticket` para classificar intent e system;
- `explicit_systems` e `SYSTEM_ALIASES` para detectar contexto explicito e canonico;
- `LocalEmbedder` e `qwen3-embedding:0.6b`;
- `build_index` e `load_index` como mecanismo interno de indice;
- `normalize_matrix` e `normalize_text` quando aplicavel;
- o padrao de CLI existente em `src/ai_service_desk/cli.py`;
- o padrao de testes pytest e CI existentes;
- o runner Dell homologado apenas quando a validacao com Ollama real trouxer evidencia adicional.

Nao criar outro classificador, outro servidor de embeddings, banco vetorial, reranker ou pipeline paralelo.

## Schema publico de knowledge

O arquivo fonte de knowledge da Fase 4 sera JSONL UTF-8. Cada linha representa um artigo e possui exatamente os seguintes campos publicos:

```json
{
  "knowledge_id": "KB-SYN-CIGAM-ACCESS-001",
  "title": "Acesso sintetico ao CIGAM",
  "question": "Nao consigo acessar o CIGAM.",
  "answer": "Procedimento sintetico aprovado para demonstracao.",
  "system": "CIGAM",
  "intent": "PROBLEMA_ACESSO",
  "tags": ["acesso", "cigam"],
  "source": "SYNTHETIC_DEMO",
  "status": "APPROVED",
  "reviewed_by": "synthetic-reviewer",
  "reviewed_at": "2026-09-07T12:00:00-03:00",
  "version": 1
}
```

### Status permitidos

```text
DRAFT
APPROVED
RETIRED
```

Somente `APPROVED` e indexavel.

### Regras de validacao

O loader deve rejeitar o arquivo inteiro quando houver qualquer artigo invalido. Nao existe importacao parcial silenciosa.

Regras minimas:

- `knowledge_id`: string unica, nao vazia, ate 120 caracteres;
- `title`: string nao vazia, ate 180 caracteres;
- `question`: string nao vazia, ate 1200 caracteres;
- `answer`: string nao vazia, ate 5000 caracteres;
- `system`: string ate 120 caracteres, podendo ser vazia para conhecimento genuinamente generico;
- `intent`: deve pertencer a `ALLOWED_INTENTS`;
- `tags`: lista de no maximo 12 strings nao vazias, cada uma com ate 60 caracteres;
- `source`: string nao vazia, ate 120 caracteres;
- `status`: um dos tres status permitidos;
- `reviewed_by`: string ate 120 caracteres;
- `reviewed_at`: string ISO 8601 com timezone quando presente;
- `version`: inteiro positivo;
- campos desconhecidos sao rejeitados para manter o contrato explicito;
- IDs duplicados sao rejeitados;
- artigo `APPROVED` exige `reviewed_by` e `reviewed_at` validos;
- `DRAFT` e `RETIRED` podem existir na fonte, mas sao excluidos antes de qualquer embedding;
- uma base sem nenhum artigo `APPROVED` e valida para auditoria, mas `knowledge-index` deve rejeitar a indexacao por nao haver conteudo oficial.

Nao existe transicao automatica de `DRAFT` para `APPROVED`.

## Encapsulamento da infraestrutura de indice

`build_index` valida internamente a presenca de `ticket_id` e `texto_busca`. A knowledge base nao adota esse modelo semanticamente.

A adaptacao deve existir somente dentro de `knowledge.py` e, se necessario, `knowledge_retrieval.py`.

A funcao interna de projecao recebe artigos `APPROVED` validados e produz um `DataFrame` privado para `build_index`.

Projecao minima:

```text
ticket_id   <- knowledge_id
texto_busca <- texto semantico derivado de title, question, system, intent e tags
```

O `DataFrame` projetado tambem preserva explicitamente:

```text
knowledge_id
title
question
answer
system
intent
tags
source
status
reviewed_by
reviewed_at
version
```

A coluna interna `ticket_id` deve ser igual a `knowledge_id` em todas as linhas. Nenhum consumidor publico de knowledge recebe `ticket_id` como identificador.

### Texto de embedding

A receita de projecao da Fase 4 e:

```text
knowledge-search-v1 = title + "\n" + question + "\n" + system + "\n" + intent + "\n" + tags_joined
```

O `answer` nao participa do embedding nesta fase. Isso evita que texto de procedimento influencie a representacao da pergunta e preserva a resposta como conteudo aprovado recuperado, nao como sinal de matching.

A string resultante e gravada somente na coluna interna `texto_busca`.

## Validacao de preservacao do answer

A reutilizacao de `build_index` so e aceita porque o indice atual persiste o registro completo projetado em `documents.jsonl`, alem de usar `texto_busca` para embedding.

A Fase 4 deve ter testes explicitos que provem:

1. `knowledge_id` e preservado apos `build_index` e `load_index`;
2. `answer` e preservado byte a byte como string logica apos o round trip;
3. `system`, `intent`, `status`, `version` e metadados de revisao permanecem recuperaveis;
4. `ticket_id == knowledge_id` na representacao privada;
5. a API de retrieval retorna `knowledge_id`, nunca `ticket_id`;
6. alterar somente o `answer` altera o hash do corpus projetado, mesmo sem alterar o embedding text, porque o documento completo faz parte de `source_hash`;
7. nenhuma linha `DRAFT` ou `RETIRED` aparece em `documents.jsonl` do indice de knowledge.

Se qualquer uma dessas propriedades nao se sustentar usando `build_index` sem alteracao, isso se torna bloqueio concreto antes de modificar `index.py`.

## Provenance obrigatoria e fail-closed

Todo indice de knowledge deve possuir, no diretorio raiz do indice, um sidecar:

```text
knowledge-provenance.json
```

O sidecar e escrito somente depois que `build_index` concluir e o manifesto interno estiver completo.

Schema minimo:

```json
{
  "version": 1,
  "domain": "APPROVED_KNOWLEDGE",
  "knowledge_schema_version": 1,
  "projection_recipe": "knowledge-search-v1",
  "approved_only": true,
  "source_hash": "<manifest.source_hash>",
  "matrix_hash": "<manifest.matrix_hash>",
  "rows": 6,
  "dimensions": 1024,
  "model": "qwen3-embedding:0.6b",
  "model_digest": "<digest homologado>",
  "index_recipe": "texto_busca-plain-v1"
}
```

### Regras fail-closed

`knowledge-search` deve rejeitar explicitamente o indice antes de qualquer resposta quando:

- `knowledge-provenance.json` estiver ausente;
- o sidecar nao for JSON valido;
- campos obrigatorios estiverem ausentes ou com tipo invalido;
- `domain != "APPROVED_KNOWLEDGE"`;
- `approved_only != true`;
- `projection_recipe != "knowledge-search-v1"`;
- `source_hash`, `matrix_hash`, `rows`, `dimensions`, `model`, `model_digest` ou `index_recipe` divergirem do `manifest.json` carregado;
- qualquer documento carregado nao possuir os campos publicos obrigatorios;
- qualquer documento tiver `status != "APPROVED"`;
- qualquer documento tiver `ticket_id != knowledge_id`;
- houver `knowledge_id` duplicado ou answer vazio.

Nao existe fallback para tratar um indice sem provenance como knowledge.

Um indice historico da Fase 2, mesmo tecnicamente carregavel por `load_index`, deve ser rejeitado por `knowledge-search` por nao possuir provenance de `APPROVED_KNOWLEDGE` valida.

Copiar um sidecar de outro indice tambem deve falhar quando os hashes ou metadados divergirem.

### Retomada de indexacao

Se `build_index` for interrompido, o indice parcial permanece sem provenance valida e portanto nao pode ser consultado como knowledge.

Ao repetir `knowledge-index` com a mesma fonte, o mecanismo atual pode retomar o checkpoint. O sidecar so e criado depois de o manifesto estar completo e de a camada de knowledge confirmar que ele corresponde a projecao atual.

Um sidecar existente e divergente nunca e sobrescrito silenciosamente. A indexacao deve falhar com mensagem explicita para que o operador escolha outro diretorio ou remova conscientemente o estado invalido.

## Retrieval de knowledge

A camada sera implementada em `knowledge_retrieval.py` e nao reutilizara `retrieve()` diretamente, porque `retrieve()` expressa semanticamente historicos nao validados e retorna campos de ticket.

Ela pode reutilizar primitivas neutras existentes, como normalizacao, aliases de sistema e operacoes de similaridade, sem criar um segundo pipeline de classificacao ou embedding.

### Ordem dos gates

Para uma query:

1. validar texto de entrada com os mesmos limites seguros do classificador;
2. classificar com `classify_ticket`;
3. detectar sistemas explicitos com `explicit_systems`;
4. se houver mais de um sistema explicito, retornar abstinencia por `CONTEXTO_AMBIGUO` sem oferecer artigo;
5. carregar somente indice com provenance `APPROVED_KNOWLEDGE` valida;
6. construir pool compativel por `system` e `intent`;
7. gerar embedding da query uma unica vez quando existir pool elegivel;
8. calcular similaridade cosseno usando a matriz normalizada carregada;
9. selecionar o maior score elegivel;
10. aceitar somente se `score >= 0.65`;
11. retornar o `answer` literal do artigo selecionado.

### Regra de system

- se a query possui exatamente um sistema explicito reconhecido, somente artigos desse sistema podem participar;
- se a classificacao recupera um sistema desconhecido que nao existe na base, a busca se abstem;
- artigos de outro sistema nunca completam pool escasso;
- quando a query nao possui sistema explicito nem recuperavel, somente artigos com `system == ""` podem participar;
- aliases canonicos existentes podem ser usados para comparar nomes, mas o artigo retorna seu `system` publico original.

Essa regra prioriza seguranca e evita oferecer FAQ especifica de um sistema quando o alvo nao foi estabelecido.

### Regra de intent

Somente artigos cujo `intent` seja igual ao `intent` classificado participam do pool.

Nao existe fallback para outro intent nesta fase.

### Threshold

O threshold oficial permanece:

```text
0.65
```

Ele nao e recalibrado na Fase 4 e continua sendo tratado como score de similaridade, nao como probabilidade.

## Contrato de resultado

O retrieval publico retorna um dicionario orientado ao dominio de knowledge.

Quando encontra conhecimento:

```json
{
  "status": "KNOWLEDGE_FOUND",
  "reason": "MATCH",
  "threshold": 0.65,
  "score": 0.81,
  "classification": {
    "intent": "PROBLEMA_ACESSO",
    "system": "CIGAM",
    "entities": {},
    "confidence": 0.9
  },
  "knowledge": {
    "knowledge_id": "KB-SYN-CIGAM-ACCESS-001",
    "title": "Acesso sintetico ao CIGAM",
    "answer": "Procedimento sintetico aprovado para demonstracao.",
    "system": "CIGAM",
    "intent": "PROBLEMA_ACESSO",
    "version": 1
  }
}
```

Quando se abstem:

```json
{
  "status": "NO_APPROVED_KNOWLEDGE",
  "reason": "BELOW_THRESHOLD",
  "threshold": 0.65,
  "classification": {}
}
```

Reasons oficiais da Fase 4:

```text
MATCH
CONTEXTO_AMBIGUO
NO_COMPATIBLE_SYSTEM
NO_COMPATIBLE_INTENT
BELOW_THRESHOLD
```

Falha de provenance, schema ou corrupcao de indice nao retorna `NO_APPROVED_KNOWLEDGE`. E erro operacional explicito e encerra a consulta, pois responder como simples ausencia esconderia um problema de seguranca ou integridade.

## Resposta literal

`format_knowledge_result` deve imprimir o `answer` armazenado sem passar por `chat`, prompt de resposta, resumo ou pos-processamento generativo.

Sao permitidos apenas elementos de apresentacao fora do answer, por exemplo titulo, sistema, versao e mensagem de abstinencia.

O valor do campo `answer` no resultado deve ser igual ao valor validado na fonte `APPROVED`.

## Arquivos previstos

Criar:

```text
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/knowledge_smoke.py
knowledge/phase4_synthetic_faq.jsonl
tests/engine/test_knowledge.py
tests/engine/test_knowledge_retrieval.py
tests/engine/test_knowledge_smoke.py
tests/test_knowledge_cli.py
.github/workflows/phase4-knowledge-smoke.yml
docs/knowledge/phase-4.md
```

Modificar somente quando necessario:

```text
src/ai_service_desk/cli.py
README.md
tests/test_workflows.py
```

Nao modificar por padrao:

```text
src/ai_service_desk/engine/index.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/classification.py
```

## CLI

Adicionar comandos:

### `knowledge-validate`

```text
knowledge-validate --file <knowledge.jsonl>
```

Valida schema e imprime somente contagens seguras:

```text
total
approved
draft
retired
```

Nao imprime answers completos por padrao.

### `knowledge-index`

```text
knowledge-index --file <knowledge.jsonl> --index <diretorio> --batch-size 10 --url <loopback>
```

Fluxo:

1. valida toda a fonte;
2. seleciona somente `APPROVED`;
3. projeta para a representacao privada;
4. chama `build_index`;
5. valida o manifesto completo;
6. cria `knowledge-provenance.json` atomico e vinculado ao manifesto.

### `knowledge-search`

```text
knowledge-search --index <diretorio> --query "Nao consigo acessar o CIGAM" --threshold 0.65 --url <loopback>
```

O default de threshold e `0.65`.

O comando falha explicitamente para indice sem provenance valida.

### `knowledge-smoke`

Executa os casos sinteticos oficiais da Fase 4 e gera somente relatorio agregado seguro.

## FAQ sintetica versionada

`knowledge/phase4_synthetic_faq.jsonl` contem apenas entidades ficticias e procedimentos explicitamente marcados como sinteticos.

O conjunto deve incluir aproximadamente 8 a 12 artigos, suficiente para cobrir:

- acesso CIGAM;
- acesso SIAGRI;
- erro CIGAM;
- erro SIAGRI;
- impressao generica;
- VPN/rede generica;
- instalacao de software generica;
- Outlook;
- pelo menos um artigo `DRAFT`;
- pelo menos um artigo `RETIRED`.

Os artigos `DRAFT` e `RETIRED` existem para provar exclusao e nunca entram no indice.

Nenhum texto sera copiado ou adaptado de ticket corporativo real.

## Smoke da competicao

O smoke oficial deve provar pelo menos estes cinco cenarios:

1. problema conhecido de acesso CIGAM encontra artigo `APPROVED` CIGAM e retorna seu `answer` literal;
2. a mesma intencao para SIAGRI nunca retorna artigo CIGAM;
3. artigo equivalente marcado `DRAFT` nao e indexado nem retornado;
4. pergunta desconhecida ou semanticamente fraca fica abaixo de `0.65` e retorna `NO_APPROVED_KNOWLEDGE`;
5. query contendo CIGAM e SIAGRI retorna `NO_APPROVED_KNOWLEDGE` com `CONTEXTO_AMBIGUO`.

Adicionar tambem gates de integridade:

6. indice historico da Fase 2 e rejeitado por ausencia de provenance de knowledge;
7. sidecar adulterado ou copiado de outro indice e rejeitado;
8. `RETIRED` nunca aparece nos documentos indexados;
9. nenhum resultado publico contem `ticket_id`;
10. o answer retornado e identico ao answer da fixture aprovada.

## Testes e TDD

A implementacao sera feita em ciclos RED -> GREEN.

Ordem recomendada:

1. schema e loader;
2. filtro `APPROVED` e projecao privada;
3. round trip por `build_index` provando preservacao de `knowledge_id` e `answer`;
4. sidecar de provenance e loader fail-closed;
5. retrieval por system/intent/threshold;
6. resposta literal;
7. CLI;
8. smoke sintetico;
9. workflow Dell e documentacao.

Cada gate relevante deve executar testes focados antes da suite completa.

No final, executar pelo menos:

```text
pytest
ruff check .
ruff format --check .
```

O workflow Dell so sera necessario para validar integracao real com `qwen3.5:4b` e `qwen3-embedding:0.6b`. Testes unitarios e CI hospedado permanecem sinteticos e nao dependem de dados corporativos.

## Privacidade e logs

Nunca versionar ou publicar:

- CSV corporativo;
- historicos reais;
- IDs corporativos;
- texto real de tickets;
- `documents.jsonl` gerado de corpus corporativo;
- `embeddings.npy` corporativo;
- relatorios com conteudo de tickets.

A Fase 4 versiona somente FAQs e queries sinteticas.

Workflows nao usam `--show-history` e nao fazem upload de relatorio corporativo.

## Fora de escopo

Nao implementar nesta fase:

- frontend;
- integracao com novo sistema de chamados;
- criacao automatica de ticket;
- execucao de acoes na maquina;
- playbooks;
- policy engine;
- triagem multi-turno;
- aprendizado automatico;
- aprovacao automatica de conhecimento;
- CMS corporativo;
- importacao automatica de historicos para FAQ;
- fine tuning;
- cloud.

## Criterios de aceite

A Fase 4 pode chegar a 95% e abrir PR quando todas as condicoes abaixo forem verdadeiras:

1. branch `phase-4-knowledge-base` contem somente alteracoes da Fase 4;
2. schema publico de knowledge esta validado;
3. `APPROVED` e o unico status indexavel;
4. projecao privada usa `build_index` sem vazar semantica de ticket para a API publica;
5. round trip comprova preservacao de `knowledge_id` e `answer`;
6. indice consultavel exige provenance `APPROVED_KNOWLEDGE` valida e vinculada ao manifesto;
7. sidecar ausente, invalido ou divergente causa erro explicito;
8. indice historico nao pode ser consultado por `knowledge-search`;
9. CIGAM nao recebe SIAGRI e vice-versa;
10. contexto ambiguo se abstem;
11. sistema desconhecido se abstem;
12. intent incompativel se abstem;
13. score abaixo de `0.65` se abstem;
14. resposta oficial e exatamente o `answer` aprovado;
15. DRAFT e RETIRED nunca produzem orientacao;
16. fixture e benchmark sao 100% sinteticos;
17. suite de testes, lint e format passam;
18. homologacao Dell passa quando executada;
19. documentacao descreve claramente que historico nao validado nao e conhecimento aprovado;
20. PR esta pronto para revisao, sem merge automatico.

A Fase 4 chega a 100% somente depois de merge explicito em `main` aprovado pelo usuario.

## Politica para bloqueios em fundacoes anteriores

Se a implementacao demonstrar que `build_index` nao preserva os campos necessarios, que `load_index` destrua metadados de knowledge ou que outra propriedade essencial nao possa ser garantida pela camada dedicada, interromper a mudanca antes de editar `index.py`, `retrieval.py` ou `classification.py`.

O bloqueio deve ser apresentado com:

1. teste reproduzivel que falha;
2. causa tecnica concreta;
3. menor alteracao necessaria na fundacao;
4. risco de regressao;
5. evidencia de que nao existe solucao razoavel apenas na camada de knowledge.

Sem esse bloqueio comprovado, as fundacoes homologadas permanecem intactas.
