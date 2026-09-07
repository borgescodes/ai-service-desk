# Fase 4: FAQ e base de conhecimento

A Fase 4 adiciona uma camada dedicada de conhecimento aprovado ao AI Service Desk. O objetivo continua sendo descobrir se o chamado precisa existir antes de abrir ou escalar um atendimento.

## Separacao entre historico e conhecimento

O retrieval historico das fases anteriores continua sendo evidencia nao validada. Um ticket antigo pode ajudar a identificar padroes e candidatos de conhecimento, mas nunca autoriza uma orientacao oficial por si mesmo.

O fluxo de conhecimento da Fase 4 e:

```text
historico nao validado
-> candidato
-> revisao humana
-> artigo APPROVED
-> retrieval de knowledge
-> answer literal aprovado
```

Nao existe promocao automatica de historico para `APPROVED`.

## Schema publico

A fonte versionada usa JSONL UTF-8 com os campos:

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

Status validos:

```text
DRAFT
APPROVED
RETIRED
```

Somente `APPROVED` pode entrar no indice e produzir orientacao oficial. `DRAFT` e `RETIRED` podem existir na fonte para revisao e historico editorial, mas sao removidos antes de qualquer embedding.

## Projecao privada para o indice

A knowledge base reutiliza `build_index` e `load_index` somente como infraestrutura interna. O dominio publico nao adota semantica de tickets.

Dentro de `knowledge.py`, os artigos aprovados sao projetados para a estrutura minima esperada pelo indice:

```text
ticket_id   <- knowledge_id
texto_busca <- title + question + system + intent + tags
```

A representacao projetada preserva todos os campos publicos, incluindo o `answer`. O `answer` nao participa do texto usado para embedding.

Os testes da fase provam o round trip por `build_index` e `load_index`, incluindo preservacao de `knowledge_id`, `answer`, `system`, `intent`, `status`, revisao e `version`. Alterar somente `answer` muda o `source_hash`, mesmo sem mudar `texto_busca`.

## Provenance fail-closed

Todo indice de knowledge possui `knowledge-provenance.json` com:

```text
domain = APPROVED_KNOWLEDGE
approved_only = true
projection_recipe = knowledge-search-v1
```

O sidecar tambem vincula `source_hash`, `matrix_hash`, linhas, dimensoes, modelo, digest e receita ao `manifest.json` do indice.

`knowledge-search` rejeita explicitamente:

- sidecar ausente ou JSON invalido;
- dominio diferente de `APPROVED_KNOWLEDGE`;
- hashes ou metadados divergentes;
- documento que nao seja `APPROVED`;
- `ticket_id` privado diferente de `knowledge_id`;
- IDs duplicados ou `answer` vazio;
- indice historico sem provenance valida.

Nao existe fallback que trate um indice historico como knowledge.

## Retrieval seguro

A consulta reutiliza a classificacao existente e o modelo de embedding local homologado. A busca aplica gates antes de oferecer qualquer orientacao:

1. contexto com mais de um sistema explicito resulta em abstinencia;
2. sistema desconhecido resulta em abstinencia;
3. nao existe fallback para outro sistema;
4. intent deve coincidir exatamente;
5. nao existe fallback para outro intent;
6. score deve atingir o threshold oficial `0.65`.

Quando nenhum gate permite resposta, o resultado e `NO_APPROVED_KNOWLEDGE`.

Quando existe match seguro, o resultado e `KNOWLEDGE_FOUND` e o texto mostrado ao usuario e exatamente o campo `answer` armazenado no artigo aprovado. O LLM nao reescreve, resume, completa ou inventa procedimento na Fase 4.

## CLI

Validar a fonte sem Ollama e sem imprimir answers:

```powershell
python -m ai_service_desk knowledge-validate `
  --file knowledge/phase4_synthetic_faq.jsonl
```

Criar o indice aprovado:

```powershell
python -m ai_service_desk knowledge-index `
  --file knowledge/phase4_synthetic_faq.jsonl `
  --index C:\ai-service-desk-data\phase-4\index `
  --url http://127.0.0.1:11434
```

Consultar conhecimento aprovado:

```powershell
python -m ai_service_desk knowledge-search `
  --index C:\ai-service-desk-data\phase-4\index `
  --query "Nao consigo acessar o CIGAM" `
  --threshold 0.65 `
  --url http://127.0.0.1:11434
```

Executar o smoke da competicao:

```powershell
python -m ai_service_desk knowledge-smoke `
  --index C:\ai-service-desk-data\phase-4\index `
  --report C:\ai-service-desk-data\phase-4\reports\smoke.json `
  --url http://127.0.0.1:11434
```

## Fixture sintetica

`knowledge/phase4_synthetic_faq.jsonl` e inteiramente ficticia. Ela cobre CIGAM, SIAGRI, impressao, VPN, instalacao de software e Outlook, alem de estados `DRAFT` e `RETIRED` usados para provar exclusao.

Nenhum texto, identificador, historico ou dado pessoal do corpus corporativo e versionado nesta fase.

## Smoke da competicao

O smoke oficial cobre pelo menos:

1. problema conhecido de acesso CIGAM encontra a FAQ CIGAM aprovada;
2. problema equivalente no SIAGRI nao recebe FAQ CIGAM;
3. conhecimento ainda em `DRAFT` nao produz orientacao;
4. sistema desconhecido se abstem;
5. CIGAM e SIAGRI explicitos no mesmo pedido resultam em contexto ambiguo e abstinencia.

O relatorio persistido e agregado. Ele nao inclui texto bruto das consultas nem conteudo de `answer`.

## Homologacao Dell

`.github/workflows/phase4-knowledge-smoke.yml` e manual e roda somente no runner homologado com labels:

```text
self-hosted, Windows, X64, ai-service-desk, ollama
```

O workflow usa a fixture sintetica versionada, verifica Python 3.14 e os modelos locais, cria o indice em `RUNNER_TEMP` e executa o smoke sem fazer upload de artifacts ou imprimir o relatorio completo.

## Limites desta fase

A Fase 4 nao implementa frontend, abertura de chamados, playbooks, policy engine, execucao de acoes, fine tuning ou integracoes externas. Esses itens pertencem a fases posteriores do roadmap.
