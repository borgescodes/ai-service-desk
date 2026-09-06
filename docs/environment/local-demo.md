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
- Sessão: `juparana-pgm\pedro.borges`
- Modo: interativo via `run.cmd`
- Serviço Windows: `Stopped` e `Disabled`

O serviço permanece desabilitado porque o contexto de serviço não enxergava o mesmo Python/Ollama e a máquina apresenta secure channel de domínio quebrado. Reparar o domínio não faz parte do escopo atual.

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

### Motor oficial com corpus sintético

Arquivo: `.github/workflows/engine-smoke.yml`

Esse workflow valida o pacote oficial, os modelos locais e o caminho de classificação, embedding, índice e retrieval usando somente fixture sintética.

### Retrieval no corpus real da Fase 2

Arquivo: `.github/workflows/real-corpus-smoke.yml`

O corpus, o índice e o relatório agregado ficam fora do checkout do runner. A convenção da Fase 2 é:

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

Não colocar esses arquivos dentro de `C:\actions-runner\_work`, de um clone do repositório ou de qualquer worktree Git.

O operador deve disponibilizar previamente `base_ti_preparada.csv` em `C:\ai-service-desk-data\phase-2\corpus\`. O workflow não baixa, copia ou publica o corpus.

A homologação real executa, em ordem:

1. auditoria do snapshot contra `docs/data/phase-2-corpus-v1.json`;
2. construção ou retomada do índice local;
3. validação de 15.542 vetores com dimensão 1024 e proveniência compatível;
4. cinco queries sintéticas para CIGAM, SIAGRI, sistema inexistente, contexto ambíguo e impressão;
5. gravação de relatório agregado no caminho local configurado.

O workflow não usa `upload-artifact`, não imprime conteúdo de tickets e não exibe o arquivo de relatório.

Todos os workflows usam `-ExecutionPolicy Bypass` somente no processo do job. Isso não altera permanentemente a Execution Policy do Windows.

## Privacidade da Fase 2

O snapshot corporativo foi preparado com mascaramento parcial por regras. Isso não equivale a anonimização completa.

Regras operacionais:

- não versionar `base_ti_preparada.csv`;
- não versionar `documents.jsonl` ou `embeddings.npy` do corpus real;
- não publicar corpus, índice ou relatório real como GitHub artifact;
- não usar `--show-history` em homologações automáticas;
- não imprimir título, descrição, `texto_busca`, histórico, `ticket_id` ou `ticket_number` nos logs;
- revisão humana continua obrigatória antes de qualquer exibição de histórico corporativo.

## Regra operacional

Não fazer polling por padrão. Depois de disparar ou identificar um run, o operador acompanha o GitHub Actions e retorna com `success` ou com o log da etapa que falhou.

## Limite arquitetural

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. O produto web futuro não deve depender conceitualmente deste notebook ou deste Ollama local.
