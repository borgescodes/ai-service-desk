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

Chamadas de chat da aplicação devem usar `think=false` quando o cliente Ollama for implementado. O smoke test já usa essa configuração.

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

## Workflow de homologação

Arquivo: `.github/workflows/local-ai-smoke.yml`

Trigger: `workflow_dispatch`

Runner: `[self-hosted, Windows, X64, ai-service-desk, ollama]`

O smoke verifica identidade do runner, Python local, `/api/tags`, presença dos dois modelos, chat com `think=false` e embedding com dimensão 1024.

O workflow usa `-ExecutionPolicy Bypass` somente no processo do job. Isso não altera permanentemente a Execution Policy do Windows.

## Regra operacional

Não fazer polling. Depois de disparar ou identificar um run, o operador acompanha o GitHub Actions e retorna com `success` ou com o log da etapa que falhou.

## Limite arquitetural

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. O produto web futuro não deve depender conceitualmente deste notebook ou deste Ollama local.
