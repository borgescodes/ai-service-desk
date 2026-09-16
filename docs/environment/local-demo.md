# Ambiente local de homologação

Este documento registra a máquina usada para desenvolvimento e demonstração local. Ele não define a arquitetura permanente do produto web.

## Máquina

- Sistema operacional: Windows 11 Pro
- Equipamento: notebook Dell
- Processador: Intel Core 7 250U
- Memória: 32 GB RAM
- GPU: Intel integrada
- Armazenamento: aproximadamente 477 GB

## Python e Ollama

- Python: 3.14.7
- Ambiente do projeto: `.venv`
- Dependências: `pip`
- Ollama: 0.33.3
- API: `http://localhost:11434`
- Chat: `qwen3.5:4b`
- Embeddings: `qwen3-embedding:0.6b`
- Dimensão validada do embedding: 1024

Chamadas de chat da aplicação usam `think=false` no classificador oficial.

## GitHub self-hosted runner

- Nome: `ai-service-desk-dell`
- Labels: `self-hosted`, `Windows`, `X64`, `ai-service-desk`, `ollama`
- Diretório: `C:\actions-runner`
- Modo: interativo via `run.cmd`
- Serviço Windows: `Stopped` e `Disabled`

O serviço permanece desabilitado porque o contexto de serviço não enxergava o mesmo Python/Ollama. Reparar o domínio não faz parte do escopo atual.

Para disponibilizar o runner:

```powershell
cd C:\actions-runner
.\run.cmd
```

A janela deve permanecer aberta e mostrar `Listening for Jobs`.

## Workflows de homologação

### Infraestrutura local

Arquivo: `.github/workflows/local-ai-smoke.yml`

Trigger: `workflow_dispatch`

Runner: `[self-hosted, Windows, X64, ai-service-desk, ollama]`

O smoke verifica identidade do runner, Python local, `/api/tags`, presença dos dois modelos, chat com `think=false` e embedding com dimensão 1024.

### Fase 15: conversational core local

Arquivo: `.github/workflows/conversational-core-smoke.yml`

Trigger: `workflow_dispatch`

Runner: `[self-hosted, Windows, X64, ai-service-desk, ollama]`

A homologação do conversational core usa explicitamente:

```powershell
$env:JUP_BUSINESS_LOCAL_QA = "1"
python -m pytest tests\web\test_local_ai_conversational_acceptance.py -q -rA
```

O fluxo LOCAL_AI homologado é:

```text
ConversationInterpreter -> backend -> ResponseGrounding -> NaturalResponseGenerator
```

O Qwen interpreta contexto e produz a resposta natural, mas identidade, policy, approval, routing, estado de request, execução e knowledge oficial continuam sendo decisões autoritativas do backend.

A telemetria do runtime registra somente tempos por estágio e contagem de chamadas Qwen. Prompt, mensagem, identidade e conteúdo conversacional não são armazenados nessa telemetria.

O budget de latência para runtime aquecido é:

- `P50 <= 8 s`
- `P90 <= 12 s`
- `P95 <= 15 s`

O aquecimento inicial do modelo e a construção do índice ficam fora dessas amostras. O budget de desempenho não autoriza remover grounding, policy, contexto ou checks de segurança.

### Motor oficial com corpus sintético

Arquivo: `.github/workflows/engine-smoke.yml`

Esse workflow valida o pacote oficial, os modelos locais e o caminho de classificação, embedding, índice e retrieval usando somente fixture sintética.

### Fase 2A: retrieval da competição

Arquivo: `.github/workflows/demo-retrieval-smoke.yml`

A Fase 2A é o gate de competição. Ela usa um subconjunto determinístico de 240 tickets reais, com 40 registros em cada grupo CIGAM, SIAGRI, impressão, acesso, software e geral.

Os arquivos ficam fora do checkout:

```text
C:\ai-service-desk-data\phase-2\
├── corpus\
│   └── base_ti_preparada.csv
└── demo\
    ├── demo_subset.csv
    ├── index\
    │   ├── manifest.json
    │   ├── documents.jsonl
    │   └── embeddings.npy
    └── reports\
        ├── subset.json
        └── smoke.json
```

O workflow:

1. valida Python 3.14;
2. instala o pacote oficial;
3. cria o subset determinístico quando ele não existe;
4. constrói ou retoma o índice de 240 embeddings;
5. valida índice de 240 x 1024, modelo, digest, receita e hash do subset;
6. executa cinco consultas sintéticas para CIGAM, SIAGRI, sistema inexistente, contexto ambíguo e impressão;
7. grava apenas relatórios agregados no Dell.

O input `rebuild=true` remove somente a raiz local da demo e reconstrói subset, índice e relatórios. O snapshot completo em `corpus\base_ti_preparada.csv` não é removido.

A seleção de 240 tickets serve para demonstrar o comportamento do produto com preparação rápida. Ela não é dataset de avaliação e não deve ser usada para afirmar precisão, recall, cobertura ou percentual de automação do corpus completo.

### Fase 2B: retrieval no corpus completo

Arquivo: `.github/workflows/real-corpus-smoke.yml`

A Fase 2B preserva a validação de escala do snapshot de 15.542 tickets. O corpus, índice e relatório agregado ficam fora do checkout:

```text
C:\ai-service-desk-data\phase-2\
├── corpus\
│   └── base_ti_preparada.csv
├── index\
│   ├── manifest.json
│   ├── documents.jsonl
│   └── embeddings.npy
└── reports\
    └── real-corpus-smoke.json
```

A homologação completa executa auditoria do snapshot, construção ou retomada do índice, validação de 15.542 vetores com dimensão 1024, cinco queries sintéticas e gravação de relatório agregado.

A Fase 2B é evidência adicional de escala. Ela não bloqueia a interface de demonstração, triagem conversacional ou demais entregas da competição depois que a Fase 2A estiver verde.

## Proteção dos dados reais

Não colocar corpus, subset ou índices dentro de `C:\actions-runner\_work`, de um clone do repositório ou de qualquer worktree Git.

O operador disponibiliza previamente `base_ti_preparada.csv` em `C:\ai-service-desk-data\phase-2\corpus\`. Os workflows não baixam, copiam para o Git nem publicam o corpus.

Nenhum workflow da Fase 2 usa `upload-artifact`, `--show-history` ou imprime conteúdo dos arquivos de relatório.

Todos os workflows usam `-ExecutionPolicy Bypass` somente no processo do job. Isso não altera permanentemente a Execution Policy do Windows.

## Privacidade da Fase 2

O snapshot corporativo foi preparado com mascaramento parcial por regras. Isso não equivale a anonimização completa.

Regras operacionais:

- não versionar `base_ti_preparada.csv`;
- não versionar `demo_subset.csv`;
- não versionar `documents.jsonl` ou `embeddings.npy` de dados reais;
- não publicar corpus, subset, índice ou relatório real como GitHub artifact;
- não usar `--show-history` em homologações automáticas;
- não imprimir título, descrição, `texto_busca`, histórico, `ticket_id` ou `ticket_number` nos logs;
- revisão humana continua obrigatória antes de qualquer exibição de histórico corporativo.

## Regra operacional

Não fazer polling por padrão. Quando o operador autorizar acompanhamento ativo, consultar o run por até a janela explicitamente combinada e interromper o acompanhamento se ela for excedida.

## Limite arquitetural

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. O produto web futuro não deve depender conceitualmente deste notebook ou deste Ollama local.
