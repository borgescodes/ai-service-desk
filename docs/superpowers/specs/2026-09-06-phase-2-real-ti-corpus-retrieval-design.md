# Fase 2 Retrieval no Corpus TI Real

## Estado

Design da Fase 2. Esta fase começa somente depois da Fase 1 integrada em `main`.

## Objetivo

Conectar o motor oficial do AI Service Desk ao snapshot preparado do histórico real de TI, construir um índice reproduzível sobre os 15.542 tickets e provar que o retrieval opera sobre esse corpus sem transformar histórico em conhecimento aprovado e sem levar dados corporativos para o Git ou para artefatos do GitHub Actions.

A Fase 2 prova ingestão, proveniência, indexação e invariantes de recuperação no corpus real. Ela não calibra qualidade ou limiar. Avaliação quantitativa de retrieval pertence à Fase 3.

## Reuso obrigatório

A Fase 2 estende os componentes já integrados na Fase 1:

- `ai_service_desk.engine.data.load_corpus` para leitura segura do corpus preparado;
- `ai_service_desk.engine.index.build_index` e `load_index` para hash, checkpoint, retomada e validação de integridade;
- `ai_service_desk.engine.ollama.LocalEmbedder` para `qwen3-embedding:0.6b`;
- `ai_service_desk.engine.retrieval.RetrievalEngine` para classificação, contexto, threshold e abstinência;
- o CLI `python -m ai_service_desk` como interface operacional;
- CI hospedado para verificações determinísticas sem dados corporativos;
- runner Dell self-hosted para homologação com corpus e modelos locais.

Não criar outro índice, outro retriever, outro formato de embedding ou outra aplicação paralela.

## Snapshot real de referência

O snapshot preparado disponível para a Fase 2 possui os seguintes fatos verificados:

| Propriedade | Valor |
| --- | ---: |
| Arquivo lógico | `base_ti_preparada.csv` |
| SHA-256 do arquivo | `26b3ca70c91db22145cf16676c0d13a8b5c847e6303ee440a0806e395b6e12bb` |
| Hash canônico usado pelo índice | `3159a3430abfd6091b84e0216cd4cf9e029817357d0109ad6bc244ff5f5ec448` |
| Registros | 15.542 |
| `ticket_id` únicos | 15.542 |
| Registros com histórico | 14.472 |
| Registros sem histórico | 1.070 |
| Colunas | 14 |
| `texto_busca` vazio | 0 |
| `ticket_id` vazio | 0 |
| `texto_busca` máximo | 6.000 caracteres |
| Registros com texto limitado | 5 |
| `status_conhecimento` | `HISTORICO_NAO_VALIDADO` em 100% das linhas |

Colunas do snapshot:

```text
ticket_id
ticket_number
title
description
created_at
catalogo
area
item
mesa
texto_busca
texto_limitado
historico_atendimento
apontamento_ids
status_conhecimento
```

A preparação histórica que originou esse snapshot registrou:

- 44.155 tickets lidos;
- 61.735 apontamentos lidos;
- 2.311 tickets abertos ou cancelados excluídos;
- 24.799 tickets fora do escopo TI excluídos;
- 1.503 tickets excluídos por regras de conteúdo sensível;
- 6.407 mensagens genéricas removidas;
- 15.542 registros preparados;
- 14.472 registros com histórico.

Esses números descrevem o snapshot atual. Uma futura atualização da base constitui outro snapshot e deve receber fingerprint e auditoria próprios.

## Decisão de dados

### Corpus real fora do Git

`base_ti_preparada.csv` não será versionado, nem mesmo no repositório privado.

Motivos:

1. o arquivo contém histórico corporativo real;
2. a preparação declara mascaramento parcial por regras, não anonimização completa;
3. ausência de padrões conhecidos de e-mail, IPv4, CPF, telefone ou termos sensíveis não prova ausência de PII ou informação confidencial;
4. Git mantém histórico durável e torna remoções posteriores mais difíceis;
5. o motor não precisa do corpus versionado para permanecer reproduzível.

Também não serão versionados ou enviados como artifact:

- `embeddings.npy` do corpus real;
- `documents.jsonl` do corpus real;
- índice completo ou parcial;
- relatórios contendo texto, identificadores de ticket ou históricos;
- exports brutos do TiFlux.

### O que pode ser versionado

Somente metadados seguros e agregados:

- fingerprint SHA-256 do snapshot;
- hash canônico do corpus;
- número de linhas e colunas;
- contagens agregadas;
- schema esperado;
- versão da receita de embedding;
- modelo, digest esperado após homologação e dimensões;
- resultado agregado das validações, sem texto ou ticket IDs.

## Diretório externo de homologação

No Dell, a Fase 2 assume um workspace fora do checkout Git. A convenção recomendada é:

```text
C:\ai-service-desk-data\phase-2\
├── corpus\
│   └── base_ti_preparada.csv
├── index\
│   ├── manifest.json
│   ├── documents.jsonl
│   └── embeddings.npy
└── reports\
```

O caminho pode ser configurável no workflow manual, mas nunca deve apontar para dentro do checkout do repositório.

O workflow não cria ou baixa o corpus. Ele valida um arquivo previamente colocado no Dell pelo operador em canal apropriado.

## Auditoria do corpus

A Fase 2 adiciona uma auditoria segura e determinística do corpus preparado.

A auditoria deve verificar pelo menos:

- arquivo legível em UTF-8 BOM com `;`;
- schema mínimo compatível com `load_corpus`;
- contagem de 15.542 linhas para o snapshot v1;
- `ticket_id` não vazio e único;
- `texto_busca` não vazio;
- `status_conhecimento = HISTORICO_NAO_VALIDADO` em todas as linhas;
- 14.472 registros com histórico para o snapshot v1;
- 5 registros marcados como `texto_limitado=true`;
- SHA-256 bruto do arquivo;
- hash canônico do corpus usado por `build_index`;
- contagens de padrões de risco reconhecidos sem imprimir os valores encontrados;
- comprimentos máximos dos campos de texto;
- nenhum conteúdo textual ou identificador no relatório seguro.

O resultado deve ser serializável como JSON agregado.

A auditoria não pode prometer anonimização. Seu relatório deve declarar explicitamente que é uma verificação por regras e que revisão humana continua obrigatória antes de exibir histórico.

## Manifest versionado do snapshot

O repositório terá um manifesto seguro, por exemplo:

```text
docs/data/phase-2-corpus-v1.json
```

Ele registra os valores esperados acima e funciona como contrato de entrada da Fase 2.

A auditoria deve poder comparar um arquivo local com esse manifesto e falhar antes da indexação quando houver divergência de fingerprint, schema ou contagens críticas.

Uma base atualizada não sobrescreve silenciosamente o manifesto v1. Ela exige novo manifesto ou atualização explícita revisada em PR.

## Indexação real

A indexação usa o `build_index` existente.

Para o snapshot v1, a conclusão precisa produzir um manifesto compatível com:

```text
rows = 15542
dimensions = 1024
model = qwen3-embedding:0.6b
recipe = texto_busca-plain-v1
complete = true
source_hash = 3159a3430abfd6091b84e0216cd4cf9e029817357d0109ad6bc244ff5f5ec448
```

O `model_digest` deve ser obtido do Ollama local no momento da homologação e permanecer coerente entre construção e consulta.

O índice continua oferecendo:

- escrita por lotes;
- checkpoint após cada lote confirmado;
- retomada em caso de interrupção;
- hash dos lotes;
- hash final da matriz;
- validação de alinhamento entre documentos e embeddings;
- bloqueio contra duas indexações simultâneas;
- recusa a corpus, modelo, digest, dimensão ou receita incompatíveis.

O índice real não é requisito do CI hospedado. Ele é artefato local reproduzível da homologação.

## Retrieval sobre o corpus real

O algoritmo da Fase 1 permanece a base. A Fase 2 não introduz reranker, RAG, LLM para gerar solução ou novo threshold.

A busca continua com:

```text
texto do usuário
→ classificação e grounding
→ embedding da consulta
→ validação do índice
→ seleção de contexto
→ barreira de sistema
→ filtro sensível
→ similaridade
→ threshold legado 0.65
→ candidatos ou abstinência
```

### Invariantes obrigatórios

1. Consulta com exatamente um sistema explícito nunca promove ticket incompatível com esse sistema.
2. Sistema explícito ausente no corpus retorna `SEM_CONTEXTO`, não resultado de outro sistema.
3. Dois sistemas explícitos retornam `CONTEXTO_AMBIGUO` sem candidatos.
4. Score abaixo de `0.65` retorna `SEM_EVIDENCIA`.
5. Resultado encontrado continua `HISTORICO_NAO_VALIDADO`.
6. Histórico real não é impresso ou persistido por padrão.
7. O workflow de homologação não imprime `ticket_id`, `ticket_number`, título, descrição, `texto_busca` ou histórico.
8. Similaridade continua apresentada como score, nunca probabilidade de solução.
9. A Fase 2 não altera `0.65` com base nos resultados observados. Calibração é Fase 3.

## Casos seguros de homologação

A homologação real deve usar frases sintéticas, nunca copiar texto de ticket para logs.

Casos mínimos:

### CIGAM

Consulta sintética menciona CIGAM explicitamente.

Aceite:

- classificação preserva `system=CIGAM`;
- status pode ser `ENCONTRADOS` ou `SEM_EVIDENCIA`;
- se houver candidatos, todos passam pela barreira de sistema;
- relatório registra somente contagens, status e scores agregados.

### SIAGRI

Mesmo contrato do caso CIGAM para `system=SIAGRI`.

### Sistema desconhecido

Consulta sintética menciona um sistema inexistente, por exemplo `XYZ`.

Aceite:

```text
status = SEM_CONTEXTO
candidates = 0
```

### Contexto ambíguo

Consulta sintética menciona CIGAM e SIAGRI.

Aceite:

```text
status = CONTEXTO_AMBIGUO
candidates = 0
```

### Impressão

Consulta sintética descreve problema de impressão sem sistema explícito.

Aceite:

- intent esperado `PROBLEMA_IMPRESSAO`;
- motor conclui sem erro;
- não existe obrigação de retornar candidato nesta fase.

Esses casos são smoke tests operacionais. Eles não são dataset de avaliação e não geram métricas de qualidade.

## Validação segura do índice

Além dos casos de busca, a homologação deve verificar sem imprimir conteúdo:

- `rows == 15542`;
- `shape == (15542, 1024)`;
- matriz finita e normalizada;
- `complete == true`;
- `source_hash` igual ao snapshot v1;
- `model`, `model_digest` e receita compatíveis;
- self-similarity de pelo menos uma linha determinística do índice próxima de 1, sem registrar texto ou identificador dessa linha.

## Interface operacional

A Fase 2 preserva o CLI da Fase 1 e adiciona somente o mínimo necessário.

Proposta:

```text
python -m ai_service_desk audit \
  --file <corpus.csv> \
  --manifest docs/data/phase-2-corpus-v1.json \
  --report <safe-report.json>
```

`audit` nunca imprime conteúdo de tickets.

Os comandos existentes continuam responsáveis por indexação e busca:

```text
python -m ai_service_desk index --file <corpus.csv> --index <index-dir>
python -m ai_service_desk search --index <index-dir> --query <texto>
```

A homologação automatizada pode usar uma função interna de validação real para não chamar `search` em modo que imprima candidatos.

## Workflow de homologação real

Criar um workflow manual separado, por exemplo:

```text
.github/workflows/real-corpus-smoke.yml
```

Responsabilidade:

1. checkout do `target_ref`;
2. verificar Python 3.14;
3. instalar projeto;
4. validar que `corpus_path` está fora do checkout;
5. executar `audit` contra o manifesto v1;
6. construir ou retomar o índice em `index_path`;
7. validar manifesto e matriz;
8. executar os casos sintéticos de invariantes;
9. gravar relatório seguro em `report_path` local;
10. imprimir somente resumo agregado.

Runner:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

O workflow é `workflow_dispatch`. Ele não faz upload de corpus, índice ou relatório como GitHub artifact.

Como o GitHub exige que um workflow manual exista no branch padrão para dispatch confiável, o workflow pode ser instalado em um PR de bootstrap da Fase 2 antes da branch de implementação, repetindo o padrão usado na Fase 1.

## CI hospedado

O CI automático continua 100% sintético.

Ele deve testar:

- auditoria com fixture segura;
- divergência de fingerprint;
- divergência de schema;
- IDs duplicados ou vazios;
- `texto_busca` vazio;
- status de conhecimento inválido;
- relatório sem conteúdo textual ou ticket IDs;
- contagem de padrões de risco sem vazamento do valor;
- validação de que path real não entra no repositório;
- invariantes de retrieval já cobertos na Fase 1;
- novos helpers de validação real usando índice sintético pequeno.

Nenhum teste hospedado depende do corpus de 15.542 tickets ou de Ollama real.

## Privacidade e logs

Regras adicionais da Fase 2:

- nunca imprimir uma linha completa do corpus em GitHub Actions;
- nunca imprimir valores que dispararam um detector de PII ou termo sensível;
- nunca anexar `safe-report.json` se ele deixar de ser estritamente agregado;
- manter `--show-history` desabilitado em homologações automáticas;
- qualquer futura interface que mostre histórico exige revisão humana e pertence a fase posterior;
- a auditoria pode dizer quantos registros acionaram uma regra, mas não quais registros;
- o scan de padrões conhecidos não é declaração de anonimização.

## Não objetivos

A Fase 2 não inclui:

- calibração do threshold 0.65;
- precisão, recall, MRR, nDCG ou hit rate;
- dataset rotulado;
- comparação de modelos de embedding;
- reranking;
- chunking de históricos;
- geração de resposta por LLM;
- promoção de histórico para base de conhecimento;
- FAQ;
- playbooks;
- execução automática;
- API, banco ou frontend;
- atualização automática a partir do TiFlux.

Esses itens pertencem a fases posteriores.

## Riscos e mitigação

### Dados reais vazarem para Git

Mitigação: corpus e índice ficam fora do checkout; `.gitignore` continua cobrindo artefatos gerados; CI verifica nomes/padrões proibidos no diff; workflow real não faz upload de artifact.

### Snapshot divergente ser indexado como se fosse v1

Mitigação: manifesto versionado com SHA-256, hash canônico e contagens críticas; `audit` falha antes do índice.

### PII residual ser interpretada como sanitizada

Mitigação: relatório declara mascaramento parcial; detectores são sinal de risco, não certificado; nenhum conteúdo real é exibido automaticamente.

### Retrieval parecer correto só porque encontra algo

Mitigação: smoke valida invariantes de contexto e integridade, não exige candidato quando não há evidência; qualidade fica para Fase 3.

### Contexto de sistema ser relaxado por escassez

Mitigação: manter barreira rígida da Fase 1 e testar CIGAM, SIAGRI, desconhecido e ambiguidade no índice real.

### Índice ficar preso após interrupção

Mitigação: reutilizar checkpoint e retomada da Fase 1; o operador só remove `index.lock` depois de confirmar que nenhuma indexação está ativa.

## Superfícies afetadas

Mudanças esperadas na implementação:

```text
src/ai_service_desk/engine/data.py
src/ai_service_desk/engine/index.py            # somente se auditoria exigir helper de metadados
src/ai_service_desk/engine/retrieval.py        # somente helpers seguros de validação, sem novo algoritmo
src/ai_service_desk/engine/corpus.py            # se a auditoria justificar módulo próprio
src/ai_service_desk/cli.py
tests/engine/test_corpus.py
tests/test_cli.py
docs/data/phase-2-corpus-v1.json
.github/workflows/real-corpus-smoke.yml
README.md
```

Não criar arquivos vazios apenas para corresponder a esta lista. O plano de implementação decide a divisão mínima de módulos.

## Critérios mensuráveis de saída

A Fase 2 só termina quando houver evidência de todos os itens:

- [ ] snapshot v1 auditado com 15.542 linhas e SHA-256 esperado;
- [ ] 15.542 `ticket_id` únicos e nenhum vazio;
- [ ] nenhum `texto_busca` vazio;
- [ ] 14.472 registros com histórico;
- [ ] 5 registros com `texto_limitado=true`;
- [ ] 100% dos registros permanecem `HISTORICO_NAO_VALIDADO`;
- [ ] auditoria gera somente relatório agregado;
- [ ] corpus real não está no Git;
- [ ] índice real não está no Git;
- [ ] nenhum corpus ou índice é publicado como artifact;
- [ ] índice real contém 15.542 vetores de dimensão 1024;
- [ ] `source_hash` corresponde ao snapshot v1;
- [ ] `model=qwen3-embedding:0.6b` e digest é consistente;
- [ ] `recipe=texto_busca-plain-v1`;
- [ ] `complete=true` e hashes do índice são válidos;
- [ ] caso CIGAM nunca retorna outro sistema;
- [ ] caso SIAGRI nunca retorna outro sistema;
- [ ] sistema desconhecido retorna `SEM_CONTEXTO` sem candidatos;
- [ ] CIGAM + SIAGRI retorna `CONTEXTO_AMBIGUO` sem candidatos;
- [ ] caso de impressão conclui com intent correto sem obrigação de candidato;
- [ ] nenhum teste altera ou calibra o threshold 0.65;
- [ ] CI hospedado passa com Python 3.14, Ruff e pytest usando somente fixtures sintéticas;
- [ ] `real-corpus-smoke.yml` passa no Dell com o snapshot v1 e Ollama real;
- [ ] relatório da homologação real não contém texto ou identificadores de tickets;
- [ ] PR final é revisado antes de merge.

## Definição de conclusão

Ao final da Fase 2, o repositório prova como reproduzir o retrieval sobre o snapshot real sem possuir o dado corporativo.

O Dell mantém localmente:

```text
corpus v1 + índice completo + relatório agregado
```

O Git mantém:

```text
código + testes sintéticos + manifesto seguro + workflow manual + documentação
```

A Fase 3 então pode avaliar e calibrar o comportamento do retrieval usando metodologia e dataset de avaliação próprios, sem misturar essa decisão com a ingestão do corpus real.
