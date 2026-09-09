# Fase 9: Integração CDM

## 1. Objetivo

A Fase 9 conecta o fluxo homologado da Fase 8 a uma API local simulada do CDM por meio de uma fronteira HTTP explícita e substituível.

O objetivo é provar o primeiro fluxo externo executável do AI Service Desk:

```text
AccessRequestContext válido
-> policy determinística
-> aprovação humana
-> revalidação de policy
-> ExecutionEngine
-> CDMActionExecutor
-> CDMAdapter
-> API local simulada do CDM
-> acesso SOLICITANTE criado ou reconciliado
-> estado final auditável no lifecycle existente
```

A Fase 9 não altera regras de autorização, não cria autenticação paralela do usuário, não introduz roteamento da Fase 10 e não permite roles privilegiadas.

## 2. Baseline e fontes canônicas

Baseline obrigatório:

```text
main = fd48e294617ea4d4cff91effeec507abbf44e4d5
Phase 8 homologated candidate = d5595a428aef5eecf0baa629f32fdb2940ee2335
baseline tests = 701 node IDs
```

O merge commit da `main` possui o mesmo tree Git homologado do candidate da Fase 8.

Fontes canônicas:

```text
docs/roadmap.md
docs/architecture/2026-09-08-policy-execution-cdm-handoff.md
docs/superpowers/specs/2026-09-08-phase-7-policy-engine-design.md
docs/superpowers/specs/2026-09-09-phase-8-controlled-approval-execution-design.md
```

Decisões herdadas e não reabertas:

- CDM é a única integração externa executável da primeira demonstração;
- identidade do usuário vem de `SessionIdentity`, nunca do texto do chat;
- apenas `SOLICITANTE` pode seguir para aprovação e execução;
- `APROVADOR`, `ADMIN` e `SUPERADMIN` continuam proibidos;
- `HIGH` não aprova automaticamente;
- `LOW` não rejeita automaticamente;
- policy é revalidada pelo `ExecutionEngine` antes da execução;
- frontend futuro nunca chama CDM diretamente;
- HTTP específico do CDM fica encapsulado em adapter;
- a API local simulada vem antes da API real.

## 3. Reuso obrigatório

A Fase 9 reutiliza sem duplicação:

```text
AccessRequestContext
SessionIdentity
PolicyEngine
PolicyDecision
RequestLifecycleService
AccessRequestRecord
InMemoryRequestRepository
ApprovalService
TechnicianAuthorizationRegistry
ExecutionEngine
ActionExecutor
ActionExecutionResult
```

A integração deve aproveitar a injeção de `ActionExecutor` já existente no `ExecutionEngine`.

Nenhuma alteração no `ExecutionEngine` é necessária para conectar o CDM. A Fase 9 cria um novo executor que implementa o contrato existente e delega HTTP ao adapter.

## 4. Núcleo da Fase 8 protegido

Os seguintes arquivos permanecem byte-idênticos durante a Fase 9, salvo bloqueio técnico reproduzível e revisão explícita desta spec:

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/confidence.py
src/ai_service_desk/engine/request_lifecycle.py
src/ai_service_desk/engine/request_repository.py
src/ai_service_desk/engine/technician_authorization.py
src/ai_service_desk/engine/approval.py
src/ai_service_desk/engine/execution.py
src/ai_service_desk/engine/controlled_execution_smoke.py
```

Blobs de referência:

```text
access_request.py = f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d
policy.py = 60a4f3ae785353009c30b37f71e1ce91865b899e
confidence.py = ffc0c212b455978f79a3591578f323ca0e9612dc
request_lifecycle.py = dfd194ff8a364a0eb0d803409dad252ced216279
request_repository.py = 5ccda3d30484729faa1a568cf64e20bfe55e595f
technician_authorization.py = ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4
approval.py = ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8
execution.py = 908ceade729daa3e18b7b604549f635b33d4688f
controlled_execution_smoke.py = e26766fdc35ff450d69a40a2516d193b7a90cb75
```

A Fase 9 deve adaptar-se ao núcleo homologado, não reescrevê-lo.

## 5. Componentes novos

Arquitetura mínima:

```text
src/ai_service_desk/integrations/__init__.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/engine/cdm_integration_smoke.py
```

Responsabilidades:

### `integrations/cdm.py`

- contratos `AccessLookup` e `AccessCreationResult`;
- erros tipados do adapter;
- `CDMAdapter` HTTP usando `requests`;
- validação estrutural de respostas;
- nenhum conhecimento de policy, aprovação, triagem ou playbook.

### `integrations/cdm_fake_api.py`

- API HTTP local simulada;
- estado apenas em memória;
- consulta por email;
- criação de acesso `SOLICITANTE`;
- autenticação de serviço para escrita;
- idempotência por `request_id`;
- IDs externos determinísticos por processo;
- respostas JSON fechadas e reproduzíveis.

### `engine/cdm_execution.py`

- `CDMActionExecutor` implementando o protocolo `ActionExecutor` existente;
- defesa em profundidade do contexto CDM;
- consulta antes da criação;
- mapeamento de resultados e erros do adapter para `ActionExecutionResult`.

### `engine/cdm_integration_smoke.py`

- smoke sintético ponta a ponta usando HTTP loopback real;
- API simulada iniciada em porta efêmera durante o smoke;
- uso do lifecycle, aprovação e `ExecutionEngine` reais da Fase 8;
- relatório agregado sem segredos.

## 6. Dependências e servidor HTTP

A Fase 9 não adiciona framework web.

O projeto já possui:

```text
requests>=2.32,<3
```

O adapter reutiliza `requests`.

A API fake usa somente biblioteca padrão do Python 3.14, preferencialmente:

```text
http.server.ThreadingHTTPServer
http.server.BaseHTTPRequestHandler
threading
json
urllib.parse
hmac.compare_digest
```

Motivos:

- nenhuma dependência nova;
- suficiente para uma API local de demonstração;
- fácil execução em Windows e Linux;
- fronteira HTTP real continua sendo exercitada.

## 7. Endereço local

Defaults operacionais:

```text
host = 127.0.0.1
port = 8765
base URL = http://127.0.0.1:8765
```

A API fake não deve escutar em `0.0.0.0` por padrão.

O host e a porta podem ser configuráveis pela CLI para desenvolvimento local.

Testes e smoke usam porta `0` para o sistema operacional selecionar uma porta efêmera.

## 8. Credencial de serviço

A credencial de serviço é distinta de `SessionIdentity`.

```text
SessionIdentity
-> quem solicitou acesso

CDM_API_TOKEN
-> qual serviço está autorizado a criar acesso no CDM
```

Regras:

- o token vem exclusivamente da variável de ambiente `CDM_API_TOKEN`;
- token vazio ou ausente impede construção operacional do adapter e inicialização da API fake pela CLI;
- o token nunca é gravado em Git;
- o token nunca aparece em relatório, exceção, log ou output de smoke;
- comparação do bearer token no simulador usa `hmac.compare_digest`;
- o `POST /api/v1/access` exige `Authorization: Bearer <token>`;
- o `GET /api/v1/access` segue o contrato canônico e não exige bearer token nesta fase.

## 9. Contrato da API fake

### 9.1 Consulta de acesso

```http
GET /api/v1/access?email=pedro.miranda@juparana.com.br
```

Sem acesso:

```json
{
  "exists": false,
  "email": "pedro.miranda@juparana.com.br"
}
```

Com acesso:

```json
{
  "exists": true,
  "email": "pedro.miranda@juparana.com.br",
  "role": "SOLICITANTE",
  "status": "ACTIVE",
  "access_id": "100001"
}
```

Regras:

- query string deve conter exatamente um `email` não vazio;
- email é normalizado com `strip().lower()` apenas para chave interna;
- a resposta devolve o email normalizado;
- `exists=false` não inclui `role`, `status` ou `access_id`;
- `exists=true` exige `role`, `status` e `access_id` válidos;
- status válido nesta fase é somente `ACTIVE`.

### 9.2 Criação de acesso

```http
POST /api/v1/access
Content-Type: application/json
Authorization: Bearer <service-token>
```

Body exato:

```json
{
  "request_id": "REQ-000184",
  "username": "pedro.miranda",
  "email": "pedro.miranda@juparana.com.br",
  "role": "SOLICITANTE"
}
```

Criação nova:

```http
201 Created
```

```json
{
  "success": true,
  "outcome": "CREATED",
  "access_id": "100001",
  "status": "ACTIVE"
}
```

Replay idempotente do mesmo `request_id` com o mesmo payload:

```http
200 OK
```

```json
{
  "success": true,
  "outcome": "REPLAYED",
  "access_id": "100001",
  "status": "ACTIVE"
}
```

Acesso já existente para o mesmo email e role, criado por outro `request_id`:

```http
409 Conflict
```

```json
{
  "success": false,
  "error_code": "CDM_ACCESS_ALREADY_EXISTS",
  "access_id": "100001",
  "status": "ACTIVE"
}
```

O adapter interpreta este caso como condição reconciliável, não como criação duplicada.

## 10. Validação do POST

Campos permitidos são exatamente:

```text
request_id
username
email
role
```

Regras:

- body deve ser objeto JSON;
- campos extras são rejeitados;
- todos os quatro campos são obrigatórios;
- `request_id` deve seguir `REQ-[0-9]{6}`;
- `username` deve ser texto não vazio;
- `email` deve ser texto não vazio;
- `role` deve ser exatamente `SOLICITANTE`;
- qualquer role privilegiada ou desconhecida retorna erro de validação e não cria estado;
- body inválido nunca consome um novo `access_id`.

## 11. Idempotência

`request_id` é a chave idempotente da API simulada.

O simulador mantém dois índices em memória:

```text
access_by_email
request_by_id
```

Regras:

1. primeiro POST válido com `request_id` novo e email sem acesso cria um único acesso;
2. mesmo `request_id` e mesmo payload retorna `REPLAYED` e o mesmo `access_id`;
3. mesmo `request_id` com payload diferente retorna `CDM_IDEMPOTENCY_CONFLICT` e não altera estado;
4. email já existente com `SOLICITANTE` e outro `request_id` retorna `CDM_ACCESS_ALREADY_EXISTS` e o mesmo `access_id`;
5. chamadas concorrentes são serializadas por lock interno da store;
6. nenhuma corrida pode criar dois `access_id` para o mesmo email;
7. contador de IDs só avança quando uma criação nova é confirmada.

A API fake não persiste estado após o encerramento do processo. Persistência real está fora desta fase.

## 12. Erros HTTP fechados

Formato:

```json
{
  "success": false,
  "error_code": "CDM_REQUEST_INVALID",
  "message": "..."
}
```

Tabela mínima:

| HTTP | `error_code` | condição |
| --- | --- | --- |
| 400 | `CDM_REQUEST_INVALID` | query/body/schema inválido |
| 401 | `CDM_SERVICE_UNAUTHORIZED` | bearer ausente ou incorreto no POST |
| 404 | `CDM_ROUTE_NOT_FOUND` | rota desconhecida |
| 409 | `CDM_ACCESS_ALREADY_EXISTS` | email já possui acesso equivalente |
| 409 | `CDM_IDEMPOTENCY_CONFLICT` | mesmo request_id com payload diferente |
| 500 | `CDM_INTERNAL_ERROR` | falha interna controlada do simulador |

Erros 500 não devem incluir traceback ou token.

## 13. Contratos do adapter

```python
@dataclass(frozen=True)
class AccessLookup:
    exists: bool
    email: str
    role: str | None
    status: str | None
    access_id: str | None

@dataclass(frozen=True)
class AccessCreationResult:
    outcome: Literal["CREATED", "REPLAYED", "ALREADY_EXISTS"]
    access_id: str
    status: str
```

Interface:

```python
class CDMAdapter:
    def get_access(self, email: str) -> AccessLookup:
        ...

    def create_access(
        self,
        request_id: str,
        username: str,
        email: str,
        role: str,
    ) -> AccessCreationResult:
        ...
```

Configuração mínima do adapter:

```text
base_url
service_token
timeout_seconds
requests.Session opcional para testes
```

Default de timeout:

```text
3.0 segundos
```

Não há retry automático de GET ou POST nesta fase.

## 14. Validação fail-closed de resposta

O adapter nunca transforma JSON arbitrário em sucesso.

Para `get_access`:

- HTTP deve ser 200;
- JSON deve ser objeto;
- `exists` deve ser `bool` exato;
- `email` deve ser texto não vazio;
- se `exists=false`, campos de acesso devem estar ausentes ou nulos conforme contrato do adapter;
- se `exists=true`, `role`, `status` e `access_id` devem ser texto válido;
- role retornada pelo simulador operacional deve ser `SOLICITANTE`;
- status deve ser `ACTIVE`.

Para `create_access`:

- 201 + `outcome=CREATED` é sucesso;
- 200 + `outcome=REPLAYED` é sucesso;
- 409 + `error_code=CDM_ACCESS_ALREADY_EXISTS` com `access_id` e `status=ACTIVE` vira `ALREADY_EXISTS`;
- qualquer combinação não prevista falha como erro de protocolo.

## 15. Erros do adapter

Hierarquia conceitual:

```text
CDMAdapterError
  CDMRequestValidationError
  CDMServiceAuthenticationError
  CDMIdempotencyConflictError
  CDMUnavailableError
  CDMProtocolError
  CDMRemoteInternalError
```

Cada erro possui `reason_code` simbólico.

Mapeamento mínimo:

```text
400 -> CDM_REQUEST_INVALID
401 -> CDM_SERVICE_UNAUTHORIZED
409 idempotency -> CDM_IDEMPOTENCY_CONFLICT
5xx -> CDM_INTERNAL_ERROR
connection/timeout -> CDM_UNAVAILABLE
schema/status inesperado -> CDM_PROTOCOL_ERROR
```

O adapter não expõe `requests.Response` para o domínio.

## 16. CDMActionExecutor

`CDMActionExecutor` implementa o protocolo `ActionExecutor` já existente.

Contrato:

```python
class CDMActionExecutor:
    def __init__(self, adapter: CDMAdapter): ...

    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult:
        ...
```

O executor exige `request.state == "EXECUTING"` assim como o fake homologado.

Antes de qualquer HTTP, valida defesa em profundidade:

```text
request.context.system == "CDM"
request.context.intent == "PROBLEMA_ACESSO"
request.context.capability == "CDM_ACCESS_REQUEST"
request.context.requested_role == "SOLICITANTE"
```

Se qualquer condição falhar:

```text
ActionExecutionResult(False, "CDM_EXECUTION_CONTEXT_INVALID")
zero HTTP calls
```

## 17. Fluxo do executor CDM

```text
EXECUTING
  ↓
validar contexto CDM
  ↓
CDMAdapter.get_access(email)
  ↓
┌───────────────────────────────┐
│ exists = true                 │
│ role = SOLICITANTE            │
│ status = ACTIVE               │
└───────────────────────────────┘
  ↓
ActionExecutionResult(
  success=True,
  result_code="CDM_ACCESS_ALREADY_EXISTS"
)

exists = false
  ↓
CDMAdapter.create_access(...)
  ↓
CREATED
-> CDM_ACCESS_CREATED

REPLAYED
-> CDM_REQUEST_REPLAYED

ALREADY_EXISTS
-> CDM_ACCESS_ALREADY_EXISTS
```

Resultados positivos são códigos simbólicos e entram no lifecycle existente como `execution_result_code`.

## 18. Mapeamento de falhas do executor

Erros conhecidos do adapter são convertidos em `ActionExecutionResult(False, reason_code)`.

Códigos mínimos:

```text
CDM_REQUEST_INVALID
CDM_SERVICE_UNAUTHORIZED
CDM_IDEMPOTENCY_CONFLICT
CDM_UNAVAILABLE
CDM_PROTOCOL_ERROR
CDM_INTERNAL_ERROR
CDM_EXISTING_ACCESS_CONFLICT
```

Exceções inesperadas não são capturadas pelo `CDMActionExecutor`. Elas sobem para o `ExecutionEngine`, que preserva o comportamento homologado de `EXECUTOR_EXCEPTION`.

Não existe retry de `FAILED` na Fase 9.

## 19. Acesso existente incompatível

Se `GET` informar acesso existente mas com role diferente de `SOLICITANTE` ou status diferente de `ACTIVE`, o executor não cria, não altera e não sobrescreve nada.

Resultado:

```text
ActionExecutionResult(False, "CDM_EXISTING_ACCESS_CONFLICT")
```

Esta regra impede o adapter de converter estado externo inesperado em sucesso silencioso.

## 20. `access_id` e lifecycle interno

A arquitetura canônica prevê `external_id` como dado acumulado futuro.

Nesta Fase 9:

- `access_id` existe no contrato do adapter e na API simulada;
- `access_id` permanece consultável via `GET /api/v1/access`;
- o `AccessRequestRecord` da Fase 8 não é expandido;
- o lifecycle interno persiste apenas o `execution_result_code` simbólico já suportado;
- nenhuma alteração em `request_lifecycle.py` ou `execution.py` é feita apenas para carregar `access_id`.

Se uma fase posterior precisar materializar `external_id` no record interno, isso exige spec explícita e migração do contrato stateful.

## 21. CLI da API simulada

Novo comando:

```text
python -m ai_service_desk cdm-api --host 127.0.0.1 --port 8765
```

Regras:

- lê `CDM_API_TOKEN` do ambiente;
- recusa iniciar se token ausente;
- não imprime token;
- bloqueia em `serve_forever()`;
- shutdown normal por interrupção do processo;
- estado reinicia vazio a cada inicialização.

## 22. Smoke ponta a ponta

Novo comando:

```text
python -m ai_service_desk cdm-integration-smoke \
  --cases tests/fixtures/phase9_cdm_integration_cases.jsonl \
  --report <path>
```

O smoke:

1. exige `CDM_API_TOKEN` no ambiente;
2. inicia API simulada em `127.0.0.1` com porta efêmera;
3. cria requests reais da Fase 8;
4. aprova com técnico autorizado;
5. executa com `ExecutionEngine(CDMActionExecutor(CDMAdapter(...)))`;
6. consulta a API para confirmar estado externo;
7. cobre idempotência diretamente pelo adapter quando necessário;
8. encerra o servidor mesmo em falha;
9. grava somente relatório agregado sem token.

Output de sucesso:

```text
CDM INTEGRATION SMOKE OK
Casos sinteticos: 6
```

## 23. Casos sintéticos obrigatórios

O fixture da Fase 9 possui exatamente seis casos:

1. `CREATE_NEW_ACCESS`
   - request aprovado de `SOLICITANTE`;
   - GET inicial sem acesso;
   - POST cria acesso;
   - request final `COMPLETED`;
   - result code `CDM_ACCESS_CREATED`.

2. `ACCESS_ALREADY_EXISTS`
   - API pré-carregada com acesso ativo;
   - executor só consulta;
   - nenhuma segunda criação;
   - request final `COMPLETED`;
   - result code `CDM_ACCESS_ALREADY_EXISTS`.

3. `IDEMPOTENT_REPLAY`
   - duas chamadas diretas de `create_access` com mesmo `request_id` e payload;
   - primeiro resultado `CREATED`;
   - segundo `REPLAYED`;
   - mesmo `access_id`;
   - exatamente um acesso armazenado.

4. `IDEMPOTENCY_CONFLICT`
   - mesmo `request_id` com payload diferente;
   - erro `CDM_IDEMPOTENCY_CONFLICT`;
   - estado externo original preservado.

5. `SERVICE_UNAUTHORIZED`
   - adapter com token incorreto;
   - request final `FAILED`;
   - result/error code `CDM_SERVICE_UNAUTHORIZED`;
   - nenhum acesso criado.

6. `REMOTE_INTERNAL_ERROR`
   - simulador injeta falha interna controlada para o caso;
   - request final `FAILED`;
   - code `CDM_INTERNAL_ERROR`;
   - nenhum segredo ou traceback na resposta.

## 24. Segurança

Regras obrigatórias:

- `access_request.py`, `policy.py` e `confidence.py` permanecem exatos;
- núcleo stateful da Fase 8 permanece exato;
- HTTP existe somente em `integrations/cdm.py`, `integrations/cdm_fake_api.py` e smoke/testes da Fase 9;
- `CDMActionExecutor` não usa `requests` diretamente;
- token não entra em `AccessRequestContext`;
- token não entra em `AccessRequestRecord`;
- token não entra em audit;
- token não entra em fixture;
- token não entra em report;
- token não entra em mensagem de exceção;
- não existe `eval`, `exec`, shell ou subprocess no runtime da integração;
- URL default é loopback;
- role de criação é fechada em `SOLICITANTE`;
- nenhum fallback transforma erro HTTP ou schema inesperado em sucesso.

## 25. Concorrência

A store da API fake usa lock local para proteger:

```text
request_by_id
access_by_email
next_access_id
```

Cenários concorrentes obrigatórios:

- dois POSTs simultâneos com mesmo `request_id` e payload produzem um `CREATED` e um `REPLAYED`, mesmo `access_id`;
- dois POSTs simultâneos com request IDs diferentes para o mesmo email produzem no máximo um acesso;
- nenhum caminho aloca dois IDs para o mesmo email.

## 26. Sem retry automático

A Fase 9 não introduz retry de side effect.

O adapter chama cada operação HTTP no máximo uma vez por invocação de método.

Motivos:

- `FAILED` continua terminal conforme Fase 8;
- retries de POST exigiriam política de reconciliação mais ampla;
- idempotência existe no servidor para segurança de repetição explícita, não para esconder indisponibilidade.

Timeout ou conexão recusada resulta em `CDM_UNAVAILABLE`.

## 27. Testes mínimos

### API fake

- GET sem acesso;
- GET com acesso;
- GET inválido;
- POST cria `SOLICITANTE`;
- POST rejeita role privilegiada;
- POST rejeita bearer ausente;
- POST rejeita bearer errado;
- replay idempotente;
- conflito de idempotência;
- acesso já existente;
- concorrência por request_id;
- concorrência por email;
- 404 fechado;
- erro 500 sem traceback/token.

### Adapter

- serialização de query e body;
- bearer apenas no POST;
- timeout configurado;
- `AccessLookup` válido;
- `AccessCreationResult` CREATED;
- REPLAYED;
- ALREADY_EXISTS;
- 400;
- 401;
- 409 idempotency;
- 5xx;
- timeout/conexão;
- JSON inválido;
- schema inválido;
- status inesperado;
- zero retry automático.

### Executor

- exige `EXECUTING`;
- contexto inválido faz zero HTTP;
- existing ativo vira sucesso;
- criação nova vira sucesso;
- replay vira sucesso;
- conflito externo vira falha;
- erros conhecidos viram result code específico;
- exceção inesperada continua sendo tratada pelo `ExecutionEngine` como `EXECUTOR_EXCEPTION`;
- policy DENY antes da execução continua produzindo zero HTTP por herança da Fase 8.

### Regressão

- todos os 701 node IDs baseline continuam presentes;
- nenhum teste histórico é removido, renomeado ou convertido em skip;
- Fase 8 security suite continua passando;
- blobs protegidos continuam exatos.

## 28. CI e homologação

A Fase 9 deve ser demonstrável em Python 3.14 sem Ollama.

Gates mínimos:

1. `python -m ruff check .`;
2. `python -m ruff format --check .`;
3. `python -m pytest -q`;
4. baseline de 701 node IDs preservado, zero ausentes;
5. blobs protegidos exatos;
6. `CDM_API_TOKEN` ausente do Git;
7. smoke oficial 6/6;
8. hosted CI de PR verde;
9. execução local do smoke em Windows ou Linux com loopback real;
10. draft PR antes de qualquer merge;
11. merge somente após evidência final explícita.

Workflow específico da Fase 9 pode rodar em `pull_request`, pois não depende de recurso exclusivo do Dell.

Se houver workflow específico, ele gera token efêmero em runtime e nunca contém token literal versionado.

## 29. Fora de escopo

Não implementar nesta fase:

- API real do CDM;
- credencial corporativa real;
- OAuth, SSO ou novo login;
- persistência da API fake em SQLite, JSON ou banco;
- retry de `FAILED`;
- fila de aprovação da Fase 10;
- roteamento automático de técnicos da Fase 10;
- integrações externas adicionais;
- frontend;
- LLM para autorização;
- alteração de policy;
- role privilegiada;
- alteração do `AccessRequestRecord` para external_id;
- observabilidade corporativa;
- deployment de produção.

## 30. Critérios de aceite

A Fase 9 só pode ser concluída quando houver evidência de que:

- uma solicitação `SOLICITANTE` aprovada pode chegar a `COMPLETED` por HTTP real contra a API simulada;
- nenhuma chamada CDM ocorre antes de `APPROVED` e da revalidação de policy;
- policy DENY continua gerando zero chamadas externas;
- contexto CDM inválido é barrado pelo executor antes de HTTP;
- API fake aceita apenas `SOLICITANTE`;
- POST exige service token;
- token não aparece em Git, logs ou reports;
- GET consulta acesso por email;
- POST cria acesso ativo;
- `request_id` fornece idempotência real;
- concorrência não duplica acesso;
- acesso já existente é reconciliado sem duplicação;
- erros 400, 401, 409, 5xx e transporte são mapeados de forma fechada;
- response schema inesperado falha fechado;
- não existe retry automático de POST;
- `ExecutionEngine` e lifecycle da Fase 8 permanecem byte-idênticos;
- todos os 701 testes históricos permanecem coletáveis;
- full pytest, Ruff e smoke passam;
- hosted CI passa;
- PR permanece draft até revisão final.

## 31. Direção para substituição pela API real

A futura API real do CDM deve substituir somente a implementação HTTP concreta atrás do mesmo contrato de domínio:

```text
CDMActionExecutor
    ↓
CDMAdapter contract
    ↓
implementação fake hoje
implementação real futuramente
```

Policy Engine, Playbooks, RequestLifecycleService, ApprovalService e ExecutionEngine não devem precisar conhecer detalhes da API real.
