# Jup Resolve, ambiente da demonstração web

## Pré-requisitos

A demonstração da Fase 12 é local, sintética e reproduzível. Ela exige:

- Python 3.14.x;
- ambiente do projeto instalado com `python -m pip install -e ".[dev]"`;
- Node 24 para lint, testes e build do frontend;
- checkout na branch/candidate da Fase 12;
- porta TCP local disponível, por padrão `8000`.

Não é necessário executar `npm install`. O frontend não possui dependências npm de runtime e não usa CDN. Ollama também não participa do roteiro final da Fase 12.

## Arquitetura da demo

```text
Browser
  -> Jup Resolve frontend
  -> FastAPI local
  -> DemoRuntime
  -> domínio homologado F1-F11
  -> CDMAdapter
  -> fake CDM HTTP local
```

### Frontend

O código fonte está em `web/src`. O build reproduzível copia os módulos estáticos para `web/dist`, que é artefato gerado e não deve ser versionado.

O frontend apresenta os estados recebidos da API. Ele não implementa Policy, Routing, Approval, Execution ou regras de Prevenção.

### Backend

O backend FastAPI resolve a identidade somente por `X-Demo-Identity` usando a allowlist sintética. Mensagens de conversa não alteram a identidade da sessão.

O browser nunca recebe token do CDM e nunca chama o fake CDM diretamente. O fake CDM é iniciado pelo backend em loopback com porta efêmera e existe apenas para provar a integração HTTP controlada da demonstração.

## Build

Na raiz do repositório:

```powershell
node web\scripts\lint.mjs
node --test web\tests\*.test.mjs
node web\scripts\build.mjs
```

O último comando deve produzir `web/dist/index.html` e os módulos/assets necessários para execução same-origin.

## Execução

No Windows, o caminho mais simples é:

```powershell
.\run-web-demo.cmd
```

O launcher valida Node, gera o build e inicia:

```powershell
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
```

Abra então `http://127.0.0.1:8000/` no navegador local.

Para validar o fluxo determinístico sem abrir o navegador:

```powershell
python -m ai_service_desk web-demo-smoke
```

A saída de sucesso contém `WEB DEMO SMOKE OK 10/10`.

## Reset

O reset existe somente em modo demo e só aceita conexão local. Ele recria o estado mutável sintético, incluindo requests, conversas, routing in-memory e fake CDM. Ele não altera arquivos, dados corporativos ou módulos homologados.

Em PowerShell:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/demo/reset
```

Resposta esperada:

```json
{"ok": true}
```

O header `X-Forwarded-For` não transforma um cliente remoto em loopback.

## Fluxos disponíveis

A demo cobre três provas principais:

1. Microsoft 365 resolvido por Knowledge APPROVED sem criar request;
2. acesso CDM com request real, `PENDING_APPROVAL`, routing para `TECH-CDM`, aprovação humana, revalidação de policy, execução via adapter e estado final do backend;
3. Prevenção calculada pelo `PatternAggregator` e `OpportunityEngine` da Fase 11.

Todos os dados usados no runtime da demonstração são sintéticos.

## Segurança operacional

- Use apenas `127.0.0.1`, `localhost` ou `::1` no comando `web-demo`.
- Não exponha a porta da demo para a rede.
- Não adicione token real ao launcher, frontend, documentação ou fixtures.
- Não substitua a identidade demo por dados corporativos reais.
- Confidence é evidência de classificação e não representa aprovação ou autorização.

## Troubleshooting

### Build web ausente

Se a inicialização informar que o build está ausente, execute:

```powershell
node web\scripts\build.mjs
```

### Porta 8000 ocupada

Escolha outra porta local:

```powershell
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8123
```

### Perfil sem acesso à Operação

Troque a identidade demo para `Técnico CDM`. A visibilidade da navegação usa `can_operate` retornado pelo backend, e ações continuam autorizadas no backend.

### Pendência não aparece

Confirme primeiro que o fluxo do CDM criou uma solicitação em `PENDING_APPROVAL` e que a identidade atual é o técnico atribuído pelo Routing. Não altere o frontend para forçar visibilidade.

### Falha de execução

Use Solicitações e a timeline para ler o estado retornado pelo backend. A UI não deve converter falha em sucesso nem repetir execução por conta própria.

### Diagnóstico rápido

Execute:

```powershell
python -m ai_service_desk web-demo-smoke
python -m pytest tests\web -q
python -m ruff check .
python -m ruff format --check .
```
