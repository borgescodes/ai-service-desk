# Fase 2A Retrieval de Demonstração para a Competição

## Estado

Design aprovado em conversa em 2026-09-07 como refinamento da Fase 2.

A Fase 2 original continua válida como trilho de escala, agora denominada Fase 2B. Ela deixa de bloquear a evolução do produto para a competição.

## Objetivo

Provar de forma rápida, segura e reproduzível os comportamentos centrais do retrieval usando um subconjunto real controlado do snapshot de 15.542 tickets, sem afirmar métricas de precisão ou cobertura sobre o corpus completo.

A Fase 2A é o gate de competição. A Fase 2B é evidência adicional de escala.

## Princípios

1. O subset real continua fora do Git.
2. O algoritmo de retrieval não muda.
3. O threshold `0.65` não muda.
4. A seleção não pode ser manual nem escolher casos depois de observar o resultado.
5. A seleção deve ser determinística e reproduzível a partir do mesmo snapshot.
6. Nenhum texto de ticket, identificador, histórico ou candidato real entra nos logs do GitHub Actions.
7. O subset de demo não é dataset de avaliação e não autoriza afirmações de precisão, recall, cobertura ou automação global.
8. Históricos continuam `HISTORICO_NAO_VALIDADO`.

## Reuso

A Fase 2A reutiliza sem duplicação:

- `load_corpus` para leitura do snapshot preparado;
- `build_index` e `load_index` para indexação e integridade;
- `LocalEmbedder` para `qwen3-embedding:0.6b` com dimensão 1024;
- `RetrievalEngine` para classificação, contexto, similaridade e abstinência;
- `ensure_external_path` para impedir dados reais dentro do checkout;
- `run_safe_queries` e `build_real_smoke_report` para projeção agregada dos resultados;
- o runner Dell self-hosted e o Ollama local.

Não criar outro retriever, outro formato de índice ou outro threshold.

## Subset de demonstração

O subset padrão terá 240 registros, divididos em seis grupos de 40:

- `cigam`
- `siagri`
- `printing`
- `access`
- `software`
- `general`

### Seleção por grupo

A seleção semântica usa somente o corpus preparado localmente. Os campos pesquisados são:

- `catalogo`
- `area`
- `item`
- `title`
- `texto_busca`

Regras de grupo:

```text
cigam: presença literal de CIGAM
siagri: presença literal de SIAGRI
printing: impressora, impressão, imprimir ou printer
access: acesso, login, autenticação ou entrar
software: instalação, instalar, software, programa ou aplicativo
general: preenchimento com registros restantes
```

A ordem dos grupos é fixa na sequência acima. Um ticket só pode pertencer a um grupo selecionado.

Dentro de cada grupo, candidatos são ordenados por:

```text
sha256(ticket_id UTF-8)
```

Os primeiros 40 ainda não utilizados são selecionados. Portanto, o mesmo snapshot e a mesma versão da receita produzem o mesmo conjunto.

Se qualquer grupo específico não possuir 40 candidatos elegíveis, a seleção falha em vez de reduzir silenciosamente o grupo.

`general` é preenchido somente depois dos cinco grupos específicos e usa todos os registros restantes ordenados pelo mesmo hash.

## Artefatos locais

A convenção da demo no Dell é:

```text
C:\ai-service-desk-data\phase-2\demo\
├── demo_subset.csv
├── index\
│   ├── manifest.json
│   ├── documents.jsonl
│   └── embeddings.npy
└── reports\
    ├── subset.json
    └── smoke.json
```

Todos permanecem fora do Git e fora de `C:\actions-runner\_work`.

## Relatório seguro da seleção

A seleção grava somente dados agregados:

```json
{
  "version": 1,
  "recipe": "competition-demo-v1",
  "source_rows": 15542,
  "selected_rows": 240,
  "per_group": 40,
  "groups": {
    "cigam": 40,
    "siagri": 40,
    "printing": 40,
    "access": 40,
    "software": 40,
    "general": 40
  },
  "source_canonical_sha256": "...",
  "subset_canonical_sha256": "..."
}
```

O relatório não contém `ticket_id`, `ticket_number`, título, descrição, `texto_busca`, histórico ou qualquer outro conteúdo de ticket.

## CLI

Adicionar comando:

```text
python -m ai_service_desk demo-subset \
  --file <base_ti_preparada.csv> \
  --output <demo_subset.csv> \
  --report <subset.json> \
  --checkout <checkout-path> \
  --per-group 40
```

Comportamento:

1. valida que `--file`, `--output` e `--report` ficam fora do checkout;
2. carrega o snapshot preparado;
3. cria o subset determinístico;
4. recusa sobrescrever `--output` existente;
5. grava CSV com UTF-8 BOM e `;`;
6. grava relatório agregado de forma atômica;
7. imprime somente resumo agregado.

O comando não cria cliente Ollama.

## Smoke da Fase 2A

A demo usa o subset gerado e o mesmo `real-smoke`, com uma diferença operacional: o gate não exige `rows == 15542` nem o hash do snapshot completo para o índice da demo. Ele exige:

```text
rows = 240
dimensions = 1024
model = qwen3-embedding:0.6b
recipe = texto_busca-plain-v1
complete = true
```

O índice deve pertencer ao hash canônico do subset gerado.

Os casos de busca permanecem sintéticos:

- CIGAM
- SIAGRI
- impressão
- sistema XYZ inexistente
- CIGAM + SIAGRI ambíguo

Aceites principais:

- CIGAM nunca promove SIAGRI;
- SIAGRI nunca promove CIGAM;
- XYZ retorna `SEM_CONTEXTO` sem candidatos;
- CIGAM + SIAGRI retorna `CONTEXTO_AMBIGUO` sem candidatos;
- impressão classifica como `PROBLEMA_IMPRESSAO`;
- qualquer resultado real continua `HISTORICO_NAO_VALIDADO`;
- nenhum conteúdo real é impresso no workflow.

## Workflow de competição

Adicionar workflow manual separado:

```text
.github/workflows/demo-retrieval-smoke.yml
```

Runner:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

Responsabilidades:

1. checkout do `target_ref`;
2. verificar Python 3.14;
3. instalar o projeto;
4. validar o snapshot v1 contra `docs/data/phase-2-corpus-v1.json`;
5. gerar ou validar `demo_subset.csv` fora do checkout;
6. construir ou retomar o índice da demo;
7. validar dimensão, modelo, digest, receita e hash do subset;
8. executar os cinco casos seguros;
9. gravar somente relatórios agregados locais;
10. não usar `upload-artifact`.

## Fase 2B

A indexação dos 15.542 tickets continua útil como evidência de escala e pode continuar em segundo plano operacional no Dell, mas não bloqueia:

- interface de demonstração;
- triagem conversacional;
- resposta útil baseada em evidência;
- decisão entre resolver e abrir chamado;
- demais fases voltadas à competição.

Quando concluída, a Fase 2B deve manter todos os critérios da spec original da Fase 2.

## Critérios de saída da Fase 2A

A Fase 2A está concluída quando:

1. seleção determinística de 240 registros passa em testes sintéticos;
2. nenhum grupo específico possui menos de 40 registros no snapshot real usado;
3. `demo-subset` não cria cliente Ollama e não imprime conteúdo real;
4. subset e índice real da demo ficam fora do Git;
5. CI hospedado em Python 3.14 passa Ruff e pytest sem dados corporativos;
6. smoke da demo no Dell termina com `success`;
7. relatório agregado confirma 240 x 1024, índice completo e os cinco casos de invariantes;
8. o PR não contém corpus real, subset real, índice real ou relatório real;
9. documentação deixa explícito que o subset é demonstração controlada e não avaliação estatística.

Após esses critérios, a equipe pode avançar para a experiência de produto sem esperar a Fase 2B.