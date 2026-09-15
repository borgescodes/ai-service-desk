# Phase 15 Conversational Core Execution Handoff

Este handoff entrega a execução da Fase 15 a outro agente. A arquitetura e o plano já foram aprovados pelo usuário. **Não reabrir decisões de produto/arquitetura sem evidência concreta de incompatibilidade com o repositório.**

## Autoridade

Ler nesta ordem antes de editar código:

1. `docs/superpowers/specs/2026-09-15-conversational-core-design.md`
2. `docs/superpowers/plans/2026-09-15-conversational-core.md`
3. este handoff

A spec é autoridade de produto, arquitetura e invariantes. O implementation plan é autoridade de execução/TDD. Este handoff resolve estado Git, ambiente, forma de trabalho com o usuário e gates operacionais.

Se houver conflito real entre este handoff e a spec/plano, preserve segurança/autoridade do backend e reporte o conflito antes de inventar uma terceira arquitetura.

## Estado Git preparado

Repositório:

```text
borgescodes/ai-service-desk
```

Branch remota já existente:

```text
phase-15-conversational-core
```

Baseline funcional obrigatório, correspondente à `main` após a Fase 14:

```text
286ded160ce014b6a032e1c28dcf9039d0f5640e
```

Planning HEAD imediatamente antes da criação deste handoff:

```text
317309be0e3d962ce900d2f3ca4367c7dfd5dc79
```

**Não resetar a branch para nenhum desses SHAs.** Os commits posteriores ao baseline contêm a spec, o implementation plan e este handoff, todos intencionais.

Antes de qualquer implementação, validar no clone/worktree de execução:

```powershell
git fetch origin
git rev-parse origin/phase-15-conversational-core
git merge-base origin/phase-15-conversational-core 286ded160ce014b6a032e1c28dcf9039d0f5640e
git diff --name-only 286ded160ce014b6a032e1c28dcf9039d0f5640e..origin/phase-15-conversational-core
git status --short
```

O `merge-base` deve ser exatamente:

```text
286ded160ce014b6a032e1c28dcf9039d0f5640e
```

Antes do primeiro edit de implementação, o diff contra o baseline deve conter somente:

```text
docs/superpowers/specs/2026-09-15-conversational-core-design.md
docs/superpowers/plans/2026-09-15-conversational-core.md
docs/superpowers/plans/2026-09-15-conversational-core-execution-handoff.md
```

Se aparecer qualquer arquivo de código nesse diff inicial, **não reutilizar a premissa de preparação limpa**. Inspecionar e reportar antes de continuar.

## Worktree e isolamento

A branch já existe remotamente. Não criar outra branch da Fase 15.

Use `superpowers:using-git-worktrees` antes de iniciar implementação se o ambiente ainda não estiver isolado. Validar primeiro a regra de `.worktrees`/`.gitignore` definida pelo skill.

No notebook do usuário, o repositório principal fica em:

```text
C:\Users\pedro.borges\ai-service-desk
```

O worktree esperado, quando criado, é:

```text
C:\Users\pedro.borges\ai-service-desk\.worktrees\phase-15-conversational-core
```

Não mexer nem excluir branches/worktrees locais não relacionados à Fase 15. Em particular, não fazer limpeza destrutiva como parte desta execução.

## Modo de execução obrigatório

Modo recomendado:

```text
superpowers:subagent-driven-development
```

Fallback quando o ambiente não comportar subagentes:

```text
superpowers:executing-plans
```

Para cada mudança de comportamento:

```text
superpowers:test-driven-development
RED -> GREEN -> REFACTOR -> commit pequeno
```

Em qualquer bug, teste inesperadamente vermelho ou comportamento divergente:

```text
superpowers:systematic-debugging
```

Antes de qualquer afirmação de conclusão/candidate pronto:

```text
superpowers:verification-before-completion
```

Executar as Tasks do implementation plan **na ordem**. Não pular testes RED para “ganhar tempo” e não agrupar a Fase 15 inteira em um único commit.

## Princípio arquitetural que não pode ser diluído

```text
LLM entende e conversa. Backend decide e executa.
```

O Qwen pode interpretar linguagem, continuidade, correções, intenção e redigir a resposta final. O Qwen não pode se tornar fonte de verdade para:

- identidade confiável;
- área/role da sessão;
- policy;
- autorização;
- approval;
- request state;
- routing final;
- técnico atribuído;
- execução;
- request ID;
- conhecimento oficial.

Hierarquia obrigatória:

```text
TRUSTED_SESSION > BACKEND > USER_EXPLICIT > MODEL_INFERRED
```

`MODEL_INFERRED` nunca satisfaz autorização.

Somente knowledge `APPROVED` produz procedimento oficial. O procedimento aprovado deve permanecer literal e ser inserido pelo backend exatamente uma vez na resposta final.

## Escopo da Fase 15

Implementar o pipeline aprovado:

```text
ConversationContext
-> ConversationInterpreter / Qwen
-> ConversationDelta
-> ContextReducer / backend
-> decisões autoritativas de domínio
-> ConversationDisposition
-> ResponseGrounding
-> NaturalResponseGenerator / Qwen
```

A Fase 15 deve entregar:

- contexto de sessão com últimos 8 turnos;
- continuidade real entre mensagens curtas;
- correções naturais como `não, falei errado, é Outlook`;
- `TOPIC_SWITCH` sem exigir `Nova conversa`;
- interpretação semântica de social / TI / out-of-scope;
- writer final livre de catálogo/enum de frases;
- fallback seguro somente quando a decisão backend já existe;
- M365 contextual reutilizando o subestado existente;
- TI geral sem knowledge -> `TECH-GENERAL`;
- falha após guidance M365 -> `TECH-M365`;
- CDM mantendo policy/approval/execution atuais;
- métricas de estágio sem conteúdo sensível;
- homologação real no Qwen local e SLO warm runtime.

## Non-goals

Não adicionar nesta fase:

- memória persistente após reload;
- banco de memória conversacional;
- fine-tuning;
- RAG sobre tickets reais como orientação oficial;
- nova integração automática além do CDM;
- browser chamando Ollama ou CDM diretamente;
- autenticação real nova;
- reescrita completa dos engines de policy/routing/approval/execution;
- resposta a assuntos fora do escopo de TI;
- state machine gigante por sistema.

## Ambiente local conhecido

Máquina de homologação:

```text
Windows 11 Pro
Dell
Intel Core 7 250U
32 GB RAM
GPU Intel integrada
Python 3.14.7
Ollama 0.33.3
```

Modelos obrigatórios:

```text
qwen3.5:4b
qwen3-embedding:0.6b
```

Endpoint local:

```text
http://localhost:11434
```

Variável correta para QA real:

```powershell
$env:JUP_BUSINESS_LOCAL_QA = "1"
```

**Não usar `JUP_RUN_LOCAL_AI_QA`.** Essa variável já causou skips em homologação anterior.

O self-hosted runner é:

```text
ai-service-desk-dell
labels: self-hosted, Windows, X64, ai-service-desk, ollama
C:\actions-runner\run.cmd
```

O usuário aceita manter o notebook ligado e `run.cmd` aberto durante a homologação.

## Protocolo obrigatório de interação com o usuário

O agente executor está explicitamente autorizado a trabalhar de forma interativa com o usuário quando uma etapa depender da máquina Windows, Ollama, worktree, Git local ou self-hosted runner.

Use este ciclo:

```text
1. enviar o comando PowerShell exato ao usuário;
2. parar;
3. pedir/aguardar a saída completa;
4. analisar a saída recebida;
5. somente então decidir o próximo comando.
```

Pode repetir esse ciclo quantas vezes forem necessárias.

Regras:

- não inferir sucesso porque “deveria funcionar”;
- não afirmar que teste/modelo/runner está OK sem saída concreta;
- não mandar uma sequência longa de comandos dependentes quando o resultado do primeiro altera o próximo passo;
- para comandos independentes e seguros, pode agrupar quando isso simplificar;
- preferir PowerShell compatível com Windows 11;
- preservar working tree e mudanças não relacionadas;
- nunca pedir ao usuário novamente informação que este handoff/spec/plano já fornece.

## Fail-closed e transacionalidade

O primeiro call do Qwen é interpretação, não decisão operacional.

Se interpreter/JSON/schema/transporte falhar:

- não criar request;
- não criar handoff;
- não avançar triage materializado por chute;
- não persistir o `ConversationDelta` proposto;
- não persistir um `ConversationContext` novo apenas porque `_context_for` foi chamado;
- retornar erro LOCAL_AI explícito conforme o plano.

O contexto novo deve ser construído sem armazenamento e somente ser persistido ao final de um turno válido.

Falha do writer é diferente: se o backend já tomou uma decisão válida, usar fallback seguro sem desfazer o resultado operacional.

## Contratos existentes que devem sobreviver

Preservar no mínimo:

- requester confiável `fulano.tal` vindo do `DemoIdentityProvider`;
- CDM solicitante -> `PENDING_APPROVAL`;
- CDM `ADMIN`/`SUPERADMIN` -> `DENIED_POLICY`;
- zero execução externa antes de approval válida;
- UBS -> `TECH-GENERAL`, confiança `LOW`, sem ação externa;
- TI geral sem knowledge -> `TECH-GENERAL`;
- M365 password guidance -> `KB-SYN-M365-PASSWORD-001` literal;
- guidance M365 falhou -> `TECH-M365`;
- `Nova conversa` limpa contexto/triage/support session state, mas preserva requests, routing, handoffs e audit já materializados;
- browser não recebe segredo nem chama Ollama/CDM diretamente.

O raw corpus de tickets continua não autoritativo. Pode apoiar linguagem/taxonomia/evaluation, nunca procedimento oficial.

## Performance e telemetria

Métricas por turno LOCAL_AI devem separar:

```text
interpretation_ms
backend_ms
retrieval_ms
generation_ms
total_turn_ms
qwen_call_count
```

Não armazenar texto de mensagens, prompts, nome/e-mail, purpose, knowledge literal ou segredos em telemetry.

Homologação de runtime aquecido:

```text
P50 <= 8 s
P90 <= 12 s
P95 <= 15 s
```

Se o SLO falhar, diagnosticar o estágio responsável. **Não relaxar threshold nem remover grounding/security/contexto para fazê-lo passar.**

## Gates locais antes de candidate

No worktree da Fase 15, executar e registrar saída real:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
node web\scripts\lint.mjs
node --test web\tests\*.test.mjs
node web\scripts\build.mjs
git diff --check
```

Registrar contagem exata de testes Python e Node.

Depois executar QA real:

```powershell
$env:JUP_BUSINESS_LOCAL_QA = "1"
python -m pytest tests\web\test_local_ai_conversational_acceptance.py -q -rA
```

E o conjunto focado:

```powershell
$env:JUP_BUSINESS_LOCAL_QA = "1"
python -m pytest `
  tests\web\test_local_ai_conversational_acceptance.py `
  tests\web\test_local_ai_semantic_acceptance.py `
  tests\web\test_business_context_runtime.py `
  -q -rA
```

Esses comandos podem ser enviados ao usuário pelo protocolo interativo acima quando o agente não estiver rodando no notebook.

## Candidate e Git

Antes do push candidate:

```powershell
git status --short
git rev-parse HEAD
```

Working tree deve estar limpo.

Push normal apenas:

```powershell
git push origin phase-15-conversational-core
```

Depois:

```powershell
git rev-parse HEAD
git rev-parse origin/phase-15-conversational-core
```

Os SHAs devem ser idênticos. Nunca force push.

Se o candidate SHA mudar depois de qualquer homologação, a evidência anterior não pode ser reutilizada automaticamente. Rerodar os checks afetados no novo SHA.

## GitHub Actions / self-hosted

O implementation plan cria:

```text
.github/workflows/conversational-core-smoke.yml
```

Após o candidate estar no remoto, disparar:

```powershell
gh workflow run conversational-core-smoke.yml --repo borgescodes/ai-service-desk --ref phase-15-conversational-core
```

Informar URL/ID do run e **não fazer polling**.

Parar e aguardar o usuário dizer exatamente:

```text
checks acabaram
```

Somente depois consultar o resultado.

Se qualquer workflow usar `ubuntu-latest` por engano quando depende de Ollama local, tratar como bug do workflow; a homologação real depende do self-hosted Windows com as labels acima.

## Guardrails Git/GitHub

Sem autorização explícita do usuário:

- não fazer force push;
- não usar reset destrutivo;
- não rebasear a branch para apagar planning commits;
- não deletar branch;
- não deletar worktree/backup não relacionado;
- não fazer merge;
- não marcar PR Ready for Review;
- não criar release/tag;
- não publicar corpus, prompts ou conversas como artifact;
- não relaxar testes de segurança para obter verde.

A execução pode criar commits pequenos e fazer o push candidate previsto no plano. Qualquer merge fica fora da autorização deste handoff.

## Stop conditions

Parar e reportar antes de continuar quando:

- baseline/merge-base não for `286ded160ce014b6a032e1c28dcf9039d0f5640e`;
- houver código inesperado no diff inicial da branch;
- spec/plano/handoff tiverem desaparecido ou sido alterados de forma incompatível;
- interpreter failure produzir side effect operacional;
- identidade/policy/request state puderem ser alterados por texto/modelo;
- APPROVED knowledge for reescrita pelo Qwen em vez de bloco literal;
- browser passar a chamar Ollama/CDM diretamente;
- surgir necessidade de nova integração automática;
- SLO exigir remoção de segurança/contexto;
- candidate SHA mudar depois da homologação;
- um comando local retornar resultado ambíguo que muda o próximo passo.

## Entrega final esperada do agente executor

Ao terminar a implementação e homologação, reportar de forma objetiva:

```text
branch
candidate SHA local/remoto
spec path
plan path
handoff path
commits da Fase 15
full pytest: contagem + PASS
ruff check: PASS
ruff format --check: PASS
frontend lint: PASS
frontend tests: contagem + PASS
frontend build: PASS
git diff --check: PASS
real Qwen acceptance: PASS + contagem
P50 / P90 / P95 observados
self-hosted workflow run URL/ID + conclusão
working tree status
```

Também resumir evidência dos cenários críticos:

```text
contexto multi-turn
correção Teams -> Outlook
topic switch Outlook -> CDM
knowledge M365 literal
M365 failure -> TECH-M365
general IT -> TECH-GENERAL
UBS LOW confidence / zero execution
CDM requester -> PENDING_APPROVAL
CDM privileged -> DENIED_POLICY
out-of-scope -> no answer/request/handoff
prompt injection -> trusted/backend state preservado
interpreter failure -> zero side effect
writer hallucination -> safe fallback
Nova conversa -> operações materializadas preservadas
```

Depois disso, parar. Não mergear a Fase 15 sem autorização explícita do usuário.