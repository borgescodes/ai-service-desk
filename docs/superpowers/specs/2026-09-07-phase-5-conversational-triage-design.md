# Fase 5: triagem conversacional

Status: desenho aprovado para materializacao da spec. Implementacao ainda nao iniciada.

Base de referencia: `main` em `491e5dd5f79dec8ff9a192a4929b48209956be3a`.

## Objetivo

A Fase 5 transforma o fluxo de pergunta unica em uma triagem conversacional multi-turno curta, controlada e segura. O motor deve descobrir contexto faltante antes de decidir se ja existe informacao suficiente para consultar a knowledge base `APPROVED` da Fase 4.

O objetivo continua sendo descobrir se o chamado precisa existir. A Fase 5 nao cria ticket, nao executa acao, nao abre playbook, nao aplica policy engine e nao implementa frontend.

Fluxo principal:

```text
mensagem do usuario
-> classify_ticket existente
-> merge deterministico no estado
-> detectar contexto faltante
-> se necessario, fazer pergunta objetiva
-> receber nova mensagem
-> resolver contexto
-> consultar knowledge APPROVED
-> devolver answer literal aprovado
```

Fluxo de falha segura:

```text
continuar apenas ate os limites aprovados
-> contexto continua insuficiente, desconhecido ou inconsistente
-> TRIAGE_ABSTAINED
```

## Fronteiras obrigatorias

A Fase 5 deve:

- reutilizar `classify_ticket`;
- reutilizar aliases e helpers existentes quando aplicavel;
- reutilizar a knowledge base e o retrieval da Fase 4;
- manter o threshold oficial em `0.65`;
- usar somente knowledge `APPROVED` como orientacao oficial;
- usar fixtures e conversas de teste 100% sinteticas;
- manter estado pequeno, isolado e sem transcript acumulado;
- ser deterministica o suficiente para testes unitarios e smoke reproduzivel.

A Fase 5 nao deve:

- criar outro classificador;
- duplicar knowledge retrieval;
- usar historicos nao validados como resposta oficial;
- criar ticket;
- executar comando ou acao na maquina;
- implementar playbooks;
- implementar policy engine;
- implementar frontend;
- alterar o threshold `0.65`;
- adicionar dados corporativos reais ao Git;
- adicionar dependencia de banco, cache global ou session store;
- usar `confidence` como regra de decisao.

`classification.py`, `retrieval.py` e `index.py` permanecem protegidos. Qualquer alteracao neles exige antes um teste bloqueante reproduzivel, causa tecnica, menor mudanca possivel e risco de regressao explicitado.

## Arquitetura escolhida

A arquitetura aprovada e uma maquina de estados deterministica sobre os motores existentes.

Novo componente principal:

```text
TriageEngine
  -> classify_ticket existente
  -> TriageState pequeno
  -> regras deterministicas de merge e missing context
  -> perguntas fixas e limitadas
  -> KnowledgeEngine da Fase 4
```

A triagem nao possui retrieval proprio, nao possui prompt proprio de classificacao e nao acessa arquivos privados do indice de knowledge.

## Extensao estritamente aditiva do KnowledgeEngine

O contrato publico atual deve permanecer valido e com o mesmo comportamento:

```text
KnowledgeEngine.search(text)
```

A Fase 5 adiciona conceitualmente:

```text
KnowledgeEngine.search_classified(text, classification)
```

A implementacao esperada e:

```text
search(text)
-> classify_ticket(text, client.chat)
-> search_classified(text, classification)
```

`search_classified()` deve executar exatamente os mesmos gates, embedding, threshold e retorno da Fase 4, apenas recebendo uma `TicketClassification` ja resolvida pela triagem para evitar uma segunda classificacao.

Regras obrigatorias:

- `search(text)` continua publico;
- nenhum caller existente precisa mudar;
- nenhuma reason, status, threshold ou semantica da Fase 4 pode mudar como efeito colateral;
- testes com os mesmos control doubles devem provar equivalencia entre `search(text)` e `classify_ticket + search_classified(text, classification)` para a mesma classificacao;
- os testes existentes da Fase 4 devem continuar passando sem alteracao de expectativa.

## Interface neutra de disponibilidade de knowledge

`TriageEngine` nao pode abrir `documents.jsonl`, matriz de embeddings, `manifest.json`, provenance ou `KnowledgeEngine.df` diretamente.

A interface aprovada sera:

```text
KnowledgeEngine.available_systems(intent) -> tuple[str, ...]
```

Contrato:

- o resultado e derivado internamente somente dos documentos `APPROVED` ja carregados e validados pelo `KnowledgeEngine`;
- valores sao unicos e ordenados de forma deterministica;
- `""` representa a existencia de knowledge generica para o intent;
- `()` significa que nao existe artigo `APPROVED` para o intent;
- a triagem recebe somente metadado de disponibilidade, nunca texto de artigo, answer, documentos ou vetores.

Regras derivadas:

```text
available_systems(intent) == ()
-> TRIAGE_ABSTAINED / NO_APPROVED_KNOWLEDGE_FOR_INTENT
-> nao perguntar system

"" in available_systems(intent)
-> system nao e obrigatorio

available_systems(intent) contem apenas sistemas nao vazios
-> system e obrigatorio antes da busca
```

Se o usuario informar explicitamente um sistema conhecido que nao possui knowledge para aquele intent, a triagem nao deve induzir o usuario a escolher outro sistema. Com contexto suficiente, a busca segue para a Fase 4 e pode terminar em `SYSTEM_MISMATCH`.

Um sistema literal nao presente em `SYSTEM_ALIASES` mas presente em `available_systems(intent)` e considerado coberto por knowledge para aquele intent. O parser especial de correcao continua restrito a aliases canonicos conhecidos.

## Estado da triagem

O estado deve ser serializavel, pequeno e versionado.

Schema conceitual:

```text
TriageState
  version: 1
  session_id: str
  status: ACTIVE | ANSWERED | ABSTAINED
  turn_count: int
  clarification_count: int
  problem_text: str
  intent: str
  system: str
  entities: dict[str, str]
  confidence: float
  pending_field: "" | "problem" | "system"
  asked_fields: tuple[str, ...]
```

### Semantica dos campos

`session_id` e opaco. Nao carrega nome, email, usuario, matricula ou qualquer identidade corporativa.

`turn_count` conta mensagens do usuario efetivamente processadas.

`clarification_count` conta perguntas emitidas pela triagem.

`problem_text` guarda somente a descricao substantiva atual do problema. Nao guarda transcript.

`intent`, `system`, `entities` e `confidence` refletem o contexto resolvido atual. `confidence` e apenas metadado e nunca participa de gates.

`pending_field` indica qual slot a pergunta anterior tentou resolver.

`asked_fields` impede a repeticao da mesma pergunta dentro do contexto atual do problema.

### O que nunca e persistido no TriageState

- transcript completo;
- lista de mensagens anteriores;
- mensagens do assistente;
- answer de knowledge;
- texto de artigo APPROVED;
- embeddings;
- scores de retrieval;
- resultados JSON completos do LLM;
- historicos de tickets;
- `ticket_id` historico;
- cadeia de raciocinio.

## Isolamento de sessao e pureza

O contrato conceitual e:

```text
step(state, message) -> new_state + public_result
```

Nao existe `global_sessions`, banco ou cache de sessoes.

Para permitir a verificacao de isolamento sem adicionar store global, a implementacao deve vincular o `TriageEngine` a um `session_id` opaco fornecido pelo caller. `step(state, message)` rejeita um estado cujo `state.session_id` seja diferente do `session_id` ao qual aquele engine esta vinculado.

O caller sera responsavel futuramente por persistir e recuperar o estado correto. A Fase 5 nao implementa essa persistencia.

Estados `ANSWERED` e `ABSTAINED` sao terminais. Chamar `step()` novamente sobre estado terminal deve falhar explicitamente e nunca reabrir a mesma triagem.

## Classificacao por turno

Cada mensagem do usuario pode ser classificada no maximo uma vez com `classify_ticket`.

A triagem nao cria outro classificador e nao executa uma segunda chamada de classificacao ao entrar na knowledge.

O merge do resultado da classificacao depende do contexto do estado e das regras abaixo.

## Regras formais de merge do estado

As regras abaixo sao obrigatorias e possuem precedencia na ordem apresentada.

### Regra 1. Estado terminal

Se `state.status` for `ANSWERED` ou `ABSTAINED`, a mensagem nao e processada. `step()` falha explicitamente.

### Regra 2. Resposta curta ao `pending_field = system`

Uma resposta curta que contenha exatamente um sistema resolvivel atualiza somente `system`.

Ela nao substitui:

- `problem_text`;
- `intent`;
- `entities`;
- `confidence` da descricao substantiva anterior.

O sistema pode ser resolvido por:

- exatamente um alias conhecido detectado pelas regras existentes;
- um sistema literal aceito pelo classificador e coberto por `available_systems(intent)`;
- uma correcao explicita aceita pelo parser conservador definido nesta spec.

Exemplo:

```text
turno 1: "nao consigo acessar"
intent = PROBLEMA_ACESSO
system = ""
pending_field = system

turno 2: "CIGAM"
intent permanece PROBLEMA_ACESSO
system = CIGAM
problem_text permanece "nao consigo acessar"
```

Uma resposta curta de sistema nao pode transformar o intent anterior em `OUTRO` apenas porque a palavra isolada foi classificada de forma diferente.

### Regra 3. Resposta ao `pending_field = problem`

A proxima mensagem nao vazia e tratada como nova descricao substantiva.

Ela substitui:

- `problem_text`;
- `intent` pelo intent da nova classificacao;
- `entities` integralmente pelas entidades da nova classificacao;
- `confidence` pela nova confidence.

`asked_fields` e `pending_field` sao limpos porque houve novo contexto de problema, mas `turn_count` e `clarification_count` nunca sao reiniciados.

`system` segue as regras de sistema da nova descricao: sistema explicito unico substitui o anterior; multiplos sistemas limpam `system` e geram ambiguidade; correcao explicita substitui; ausencia de nova evidencia de sistema preserva o sistema ja resolvido, pois ele continua sendo contexto conversacional fornecido anteriormente.

### Regra 4. Nova descricao substantiva fora de `pending_field = problem`

Uma mensagem que nao seja apenas uma resposta curta de slot e apresente nova descricao do problema substitui o contexto substantivo atual.

Ao substituir `problem_text`:

- `problem_text` recebe somente a nova mensagem substantiva;
- `intent` e substituido pelo novo intent, inclusive se mudar;
- `entities` antigas sao descartadas integralmente;
- `entities` passam a ser somente as extraidas da nova descricao;
- `confidence` e substituida;
- `pending_field` e limpo;
- `asked_fields` e limpo para o novo contexto de problema;
- `turn_count` e `clarification_count` sao preservados;
- `system` e substituido se a nova mensagem trouxer sistema explicito unico ou correcao explicita;
- `system` e limpo se a nova mensagem trouxer mais de um sistema explicito sem correcao unica;
- se a nova mensagem nao trouxer nenhuma nova evidencia de sistema, o sistema anterior e preservado.

Exemplo:

```text
"nao consigo acessar o CIGAM"
-> intent = PROBLEMA_ACESSO
-> system = CIGAM

"na verdade o problema e que o sistema trava ao salvar"
-> problem_text e substituido
-> intent pode mudar para ERRO_SISTEMA
-> entities do problema anterior sao removidas
-> system CIGAM e preservado porque nao houve nova evidencia de outro sistema
```

Nenhuma entity antiga sobrevive por merge cumulativo quando `problem_text` e substituido.

### Regra 5. Novo system explicito unico

Quando a mensagem atual trouxer exatamente um sistema explicito unico, ele substitui `state.system`.

Isso vale tanto para uma descricao substantiva quanto para uma resposta de slot.

### Regra 6. Multiplos systems explicitos

Se a mensagem trouxer mais de um sistema explicito e nao corresponder ao parser conservador de correcao, `system` deve ser limpo e o resultado deve tratar `AMBIGUOUS_SYSTEM`.

Nunca se escolhe automaticamente o primeiro, o ultimo ou o sistema que possui maior score de knowledge.

### Regra 7. Mudanca de intent

Mudanca de intent so ocorre por nova descricao substantiva. Uma resposta curta a `pending_field = system` nunca altera o intent preservado.

Quando o intent muda por nova descricao substantiva, entities antigas sao descartadas. A disponibilidade de knowledge e recalculada para o novo intent.

## Parser conservador de correcao de system

O parser de correcao nao e um parser generico de linguagem natural.

Ele aceita somente um padrao inequivoco equivalente a:

```text
nao e <SYSTEM_A>, e <SYSTEM_B>
```

Requisitos cumulativos:

- `<SYSTEM_A>` e `<SYSTEM_B>` devem mapear de forma unica para aliases canonicos presentes em `SYSTEM_ALIASES`;
- os dois sistemas devem ser diferentes;
- deve existir exatamente um sistema negado e exatamente um sistema afirmado;
- a estrutura de negacao e afirmacao deve ser reconhecida de forma deterministica;
- nenhum terceiro sistema explicito pode estar presente.

Quando aceito, `SYSTEM_B` substitui o system anterior.

Quando qualquer requisito falhar, nao ha inferencia. Se a mensagem contiver CIGAM e SIAGRI sem correcao inequivoca, o resultado continua `AMBIGUOUS_SYSTEM`.

O parser nao interpreta frases vagas, preferencias, contexto temporal ou intencao implicita.

## Deteccao do que falta

`missing_fields` nao e persistido. E derivado do estado atual e da interface `available_systems(intent)`.

### Problema insuficiente

`intent == OUTRO` e tratado como problema ainda nao suficientemente determinado para uma busca oficial.

Se `problem` ainda nao foi perguntado no contexto atual e os limites permitem, retorna:

```text
NEEDS_CLARIFICATION / MISSING_PROBLEM
```

Pergunta fixa:

```text
O que esta acontecendo?
```

Se `problem` ja foi perguntado e a nova descricao continua sem intent utilizavel, termina em:

```text
TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM
```

`confidence` nunca altera essa decisao.

### Nenhuma knowledge APPROVED para o intent

Se `available_systems(intent) == ()`, nao se pergunta system.

Resultado terminal:

```text
TRIAGE_ABSTAINED / NO_APPROVED_KNOWLEDGE_FOR_INTENT
```

### Knowledge generica

Se `""` estiver em `available_systems(intent)`, system nao e obrigatorio. A busca pode prosseguir sem system, preservando o comportamento generico da Fase 4.

### Knowledge somente por system especifico

Se houver artigos `APPROVED` para o intent e todos tiverem `system != ""`, system e obrigatorio.

Se `state.system == ""`, a triagem pergunta uma vez:

```text
NEEDS_CLARIFICATION / MISSING_SYSTEM
```

Pergunta fixa:

```text
Qual sistema esta com o problema?
```

### System ambiguo

Uma mensagem com multiplos sistemas explicitos, sem correcao inequivoca, resulta inicialmente em:

```text
NEEDS_CLARIFICATION / AMBIGUOUS_SYSTEM
```

se `system` ainda puder ser perguntado dentro dos limites.

Se `system` ja foi perguntado no mesmo contexto e a ambiguidade permanecer, termina em:

```text
TRIAGE_ABSTAINED / AMBIGUOUS_SYSTEM
```

### System desconhecido

System desconhecido significa um literal que:

- nao resolve para alias conhecido em `SYSTEM_ALIASES`; e
- nao aparece em `available_systems(intent)`.

Na primeira ocorrencia, se `system` ainda nao foi perguntado e os limites permitem:

```text
NEEDS_CLARIFICATION / UNKNOWN_SYSTEM
```

A pergunta deve solicitar correcao objetiva do sistema, sem sugerir qual sistema escolher.

Se o usuario ja teve uma oportunidade de corrigir `system` no mesmo contexto e continua fornecendo system desconhecido, o resultado e terminal:

```text
TRIAGE_ABSTAINED / UNKNOWN_SYSTEM
```

## Limites de conversa

Constantes aprovadas:

```text
MAX_USER_TURNS = 3
MAX_CLARIFICATIONS = 2
```

Semantica precisa:

- uma mensagem e aceita quando `turn_count < MAX_USER_TURNS` antes do processamento;
- a mensagem aceita incrementa `turn_count` e e processada integralmente;
- portanto o terceiro turno do usuario pode resultar em `KNOWLEDGE_FOUND`;
- um quarto turno e rejeitado;
- se, apos processar o terceiro turno, ainda seria necessario emitir nova pergunta, a triagem termina em `TRIAGE_ABSTAINED / MAX_TURNS` em vez de emitir pergunta que exigiria quarto turno;
- uma nova pergunta so pode ser emitida quando `clarification_count < MAX_CLARIFICATIONS`;
- ao emitir pergunta, `clarification_count` e incrementado;
- se seria necessaria uma terceira pergunta, termina em `TRIAGE_ABSTAINED / MAX_CLARIFICATIONS`;
- cada campo pode ser perguntado no maximo uma vez dentro do contexto atual de `problem_text`;
- quando uma nova descricao substantiva substitui `problem_text`, `asked_fields` e limpo, mas os contadores globais nao reiniciam.

Cenario que obrigatoriamente deve funcionar:

```text
turno 1: preciso de ajuda
-> pergunta 1
turno 2: nao consigo acessar
-> pergunta 2
turno 3: CIGAM
-> KNOWLEDGE_FOUND, se houver knowledge APPROVED suficiente
```

## Query enviada para knowledge

A triagem nao pode otimizar semanticamente a query para tentar ultrapassar `0.65`.

A query pode conter somente:

- `problem_text` atual fornecido pelo usuario;
- o system resolvido que tambem veio da conversa, quando necessario para refletir uma resposta curta de esclarecimento ou uma correcao posterior.

A triagem nao pode adicionar:

- labels de intent como `PROBLEMA_ACESSO`;
- tags de knowledge;
- sinonimos artificiais;
- termos extras sugeridos pelo classificador;
- frases de reforco semantico;
- answer ou title de artigos;
- texto historico.

### Reconciliacao lexical de system

Quando `problem_text` ja contem exatamente o mesmo system resolvido, ele e usado sem duplicar o system.

Quando `problem_text` nao contem system explicito e o system foi obtido em resposta curta, o system pode ser acrescentado uma unica vez como contexto literal separado.

Quando `problem_text` contem sistemas antigos ou multiplos que foram posteriormente corrigidos ou desambiguados pelo usuario, a query builder pode somente remover spans de aliases conhecidos conflitantes e acrescentar o system final resolvido. Essa operacao e lexical e deterministica. Nao pode reescrever o restante do problema, adicionar sinonimos, alterar intent textual ou inserir termos destinados a aumentar similaridade.

Devem existir testes provando que:

```text
"Nao consigo acessar o CIGAM"
```

e

```text
"Nao consigo acessar"
-> "CIGAM"
```

chegam a mesma knowledge `APPROVED` esperada, mantendo threshold `0.65` e sem adicionar labels artificiais.

## Quando chamar knowledge retrieval

A knowledge so e consultada quando:

- o estado esta `ACTIVE`;
- o intent e utilizavel;
- existe alguma knowledge `APPROVED` para aquele intent;
- system obrigatorio foi resolvido quando necessario;
- nao existe ambiguidade de system pendente;
- os limites nao exigem abstencao antes da busca.

A Fase 5 constroi uma `TicketClassification` a partir do estado resolvido e chama `KnowledgeEngine.search_classified(query_text, classification)`.

O threshold continua pertencendo ao `KnowledgeEngine` e permanece `0.65`. A triagem nao possui threshold alternativo.

Se a Fase 4 retornar `KNOWLEDGE_FOUND`, a Fase 5 termina em estado interno `ANSWERED` e retorna o answer literal aprovado.

Se a Fase 4 retornar `NO_APPROVED_KNOWLEDGE`, a Fase 5 nao inventa procedimento e termina em estado interno `ABSTAINED`. Quando a causa vier do retrieval da Fase 4, a reason original deve ser preservada, por exemplo:

- `SYSTEM_MISMATCH`;
- `INTENT_MISMATCH`;
- `BELOW_THRESHOLD`;
- `UNKNOWN_SYSTEM`;
- `CONTEXTO_AMBIGUO`, se ainda alcançavel por defesa em profundidade.

## Contrato publico de resultado

Existem exatamente tres `status` publicos da triagem.

### `NEEDS_CLARIFICATION`

Semantica: ainda existe uma unica pergunta objetiva permitida que pode tornar o contexto suficiente.

Campos publicos conceituais:

```text
status = NEEDS_CLARIFICATION
reason = MISSING_PROBLEM | MISSING_SYSTEM | AMBIGUOUS_SYSTEM | UNKNOWN_SYSTEM
question = texto fixo e objetivo
knowledge = null
```

### `KNOWLEDGE_FOUND`

Semantica: a knowledge da Fase 4 encontrou artigo `APPROVED` acima dos mesmos gates e threshold existentes.

```text
status = KNOWLEDGE_FOUND
reason = MATCH
question = null
knowledge = objeto publico da Fase 4
```

O `answer` retornado e literal. Ele nunca e persistido no `TriageState`.

### `TRIAGE_ABSTAINED`

Semantica: a triagem terminou sem orientacao oficial suficiente e nao fara nova pergunta na mesma sessao.

Reasons da propria triagem:

```text
UNRESOLVED_PROBLEM
NO_APPROVED_KNOWLEDGE_FOR_INTENT
AMBIGUOUS_SYSTEM
UNKNOWN_SYSTEM
MAX_TURNS
MAX_CLARIFICATIONS
```

Reasons originadas na Fase 4 devem ser preservadas quando o retrieval ja tiver sido chamado.

Nenhum resultado publico inclui transcript completo, historico de ticket, `ticket_id` historico, embeddings ou cadeia de raciocinio.

## Smoke cases obrigatorios

A fixture e as conversas sao 100% sinteticas.

### 1. System ausente resolvido no segundo turno

```text
U: Nao consigo acessar.
A: Qual sistema esta com o problema?
U: CIGAM
=> KNOWLEDGE_FOUND / KB-SYN-CIGAM-ACCESS-001
```

### 2. Contexto completo no primeiro turno

```text
U: Nao consigo acessar o CIGAM.
=> KNOWLEDGE_FOUND / KB-SYN-CIGAM-ACCESS-001
clarification_count = 0
```

### 3. Ambiguidade resolvida

```text
U: CIGAM e SIAGRI estao sem acesso.
=> NEEDS_CLARIFICATION / AMBIGUOUS_SYSTEM
U: SIAGRI
=> KNOWLEDGE_FOUND / KB-SYN-SIAGRI-ACCESS-001
```

### 4. Correcao explicita

```text
U: CIGAM e SIAGRI estao sem acesso.
=> NEEDS_CLARIFICATION / AMBIGUOUS_SYSTEM
U: Nao e CIGAM, e SIAGRI.
=> KNOWLEDGE_FOUND / KB-SYN-SIAGRI-ACCESS-001
```

### 5. System desconhecido corrigido

```text
U: O sistema XYZ esta sem acesso.
=> NEEDS_CLARIFICATION / UNKNOWN_SYSTEM
U: CIGAM
=> KNOWLEDGE_FOUND / KB-SYN-CIGAM-ACCESS-001
```

### 6. System desconhecido permanece desconhecido

```text
U: O sistema XYZ esta sem acesso.
=> NEEDS_CLARIFICATION / UNKNOWN_SYSTEM
U: XYZ
=> TRIAGE_ABSTAINED / UNKNOWN_SYSTEM
```

### 7. Sem knowledge APPROVED suficiente

```text
U: O CIGAM fecha em uma rotina ficticia ainda em revisao.
=> TRIAGE_ABSTAINED
```

Nenhum artigo `DRAFT` ou `RETIRED` pode aparecer.

### 8. Knowledge generica sem pergunta redundante

```text
U: A impressora ficticia nao imprime.
=> KNOWLEDGE_FOUND / KB-SYN-PRINT-001
```

Nao perguntar system.

### 9. Isolamento entre sessoes

```text
Sessao A: Nao consigo acessar.
=> aguarda system

Sessao B: A impressora ficticia nao imprime.
=> knowledge de impressao

Sessao A: CIGAM
=> knowledge de CIGAM
```

Nenhum estado de B pode influenciar A.

### 10. Anti-loop

```text
U: Preciso de ajuda.
=> NEEDS_CLARIFICATION / MISSING_PROBLEM
U: Nao sei explicar.
=> TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM
```

Nao repetir a mesma pergunta.

## Testes unitarios obrigatorios alem do smoke

Os testes devem cobrir pelo menos:

- equivalencia retrocompativel de `search()` e `search_classified()`;
- `available_systems(intent)` sem expor internals;
- nenhum artigo para intent evita pergunta inutil de system;
- knowledge generica nao exige system;
- knowledge somente especifica exige system;
- resposta curta de system preserva intent e problem_text;
- nova descricao substantiva substitui problem_text;
- nova descricao substantiva remove entities antigas;
- mudanca de intent recalcula disponibilidade;
- novo system explicito substitui anterior;
- multiplos systems sem correcao ficam ambiguos;
- parser de correcao aceita apenas o padrao conservador aprovado;
- parser rejeita terceiro system, aliases desconhecidos e frases vagas;
- terceiro turno pode resolver e retornar `KNOWLEDGE_FOUND`;
- quarto turno e rejeitado;
- terceira pergunta nunca e emitida;
- campo nao e perguntado duas vezes no mesmo contexto;
- `confidence` nao altera nenhuma transicao;
- query nao contem label artificial de intent;
- fluxo single-turn e fluxo two-turn chegam a mesma knowledge esperada;
- threshold permanece `0.65`;
- session mismatch e rejeitado;
- `ANSWERED` e `ABSTAINED` sao terminais;
- estado nao contem answer;
- resultado publico nao contem transcript;
- nenhum `ticket_id` historico aparece.

## Privacidade e dados de teste

Nenhuma conversa real, ticket real, identificador pessoal, texto corporativo, report com conteudo corporativo, indice real ou embedding real entra no Git.

O smoke pode persistir apenas metadados agregados seguros, por exemplo:

```text
case_name
expected_status
actual_status
reason
expected_knowledge_id sintetico
actual_knowledge_id sintetico
turn_count
clarification_count
passed
```

O report nao deve persistir mensagens, transcript nem `answer`.

## Arquivos previstos para a implementacao

Criar:

```text
src/ai_service_desk/engine/triage.py
src/ai_service_desk/engine/triage_smoke.py
tests/engine/test_triage.py
tests/engine/test_triage_smoke.py
tests/test_triage_cli.py
tests/fixtures/phase5_triage_conversations.jsonl
.github/workflows/phase5-triage-smoke.yml
docs/triage/phase-5.md
```

Modificar:

```text
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/cli.py
tests/test_workflows.py
README.md
```

Nao modificar sem bloqueio tecnico reproduzivel:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/index.py
```

`src/ai_service_desk/engine/knowledge.py` tambem nao precisa ser alterado pelo desenho atual. A disponibilidade de sistemas e exposta pelo `KnowledgeEngine`, que ja carrega somente um indice de knowledge com provenance fail-closed.

## Workflow de homologacao

A Fase 5 deve possuir workflow manual para o Dell homologado, seguindo o padrao das fases anteriores:

- `workflow_dispatch`;
- runner `self-hosted`, `Windows`, `X64`, `ai-service-desk`, `ollama`;
- Python 3.14;
- Ollama apenas em loopback;
- knowledge sintetica da Fase 4;
- conversas sinteticas da Fase 5;
- sem `upload-artifact`;
- sem imprimir transcript ou answer;
- report apenas agregado e local.

## Invariantes de homologacao

Antes de considerar a Fase 5 homologada, todas as invariantes abaixo devem ser verdadeiras:

- nenhum resultado publico contem transcript completo;
- nenhum `answer` e persistido no `TriageState`;
- nenhum `ticket_id` historico aparece;
- nenhuma resposta `DRAFT` ou `RETIRED` aparece;
- nenhuma sessao influencia outra;
- estado `ANSWERED` ou `ABSTAINED` e terminal;
- threshold continua `0.65`;
- historico nao validado nunca vira resposta oficial;
- `classification.py`, `retrieval.py` e `index.py` permanecem intactos, salvo bloqueio tecnico aprovado;
- todos os 177 testes existentes no commit base continuam passando;
- todos os novos testes da Fase 5 passam;
- smoke sintetico da Fase 5 passa no Dell homologado.

## Riscos de regressao e mitigacao

### Regressao da Fase 4

Risco: alterar `KnowledgeEngine` ao adicionar `search_classified()`.

Mitigacao: extensao estritamente aditiva, equivalencia com control doubles e todos os testes anteriores obrigatorios.

### Segunda classificacao

Risco: a triagem classificar e depois `KnowledgeEngine.search()` classificar novamente.

Mitigacao: Fase 5 usa `search_classified()` e cada mensagem e classificada no maximo uma vez.

### Vazamento entre sessoes

Risco: estado compartilhado acidentalmente.

Mitigacao: sem store global, `session_id` opaco, engine vinculado a uma sessao e rejeicao de mismatch.

### Loop de perguntas

Risco: repetir esclarecimentos indefinidamente.

Mitigacao: `MAX_USER_TURNS = 3`, `MAX_CLARIFICATIONS = 2`, `asked_fields` e estados terminais.

### Contexto obsoleto

Risco: entities ou intent de problema antigo sobreviverem a nova descricao.

Mitigacao: substituicao atomica de `problem_text`, intent, entities e confidence em nova descricao substantiva; system segue regras explicitas de evidencia.

### Correcao interpretada como ambiguidade

Risco: `nao e CIGAM, e SIAGRI` ser tratado como dois systems equivalentes.

Mitigacao: parser limitado ao padrao canonico aprovado. Qualquer frase fora do contrato continua ambigua.

### Manipulacao da query para aumentar score

Risco: adicionar labels ou termos artificiais para superar `0.65`.

Mitigacao: query limitada a texto real do problema e system real fornecido na conversa, com apenas reconciliacao lexical deterministica de aliases conflitantes apos correcao explicita.

## Criterios de aceite da implementacao

A Fase 5 estara pronta para homologacao quando:

1. `KnowledgeEngine.search()` continuar retrocompativel;
2. `search_classified()` evitar segunda classificacao sem duplicar retrieval;
3. `available_systems()` encapsular a disponibilidade de knowledge sem expor internals;
4. a maquina de estados obedecer integralmente as regras de merge desta spec;
5. os tres estados publicos tiverem transicoes deterministicas;
6. os 10 smoke cases forem cobertos;
7. os limites de 3 turnos e 2 esclarecimentos forem respeitados sem impedir resolucao no terceiro turno;
8. nenhuma query receber labels artificiais ou alteracao de threshold;
9. todas as invariantes de privacidade e isolamento forem verificadas;
10. os 177 testes existentes continuarem verdes e os novos testes passarem.
