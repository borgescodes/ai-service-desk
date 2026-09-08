# Fase 5: triagem conversacional

Status: desenho aprovado. Implementacao ainda nao iniciada.

Base de referencia: `main` em `491e5dd5f79dec8ff9a192a4929b48209956be3a`.

## Objetivo

A Fase 5 transforma o fluxo de pergunta unica em uma triagem conversacional multi-turno curta, controlada e segura. O motor deve descobrir contexto faltante antes de decidir se existe informacao suficiente para consultar a knowledge base `APPROVED` da Fase 4.

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

O objetivo continua sendo descobrir se o chamado precisa existir. A Fase 5 nao cria ticket, nao executa acao, nao abre playbook, nao aplica policy engine e nao implementa frontend.

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
- adicionar banco, cache global ou session store;
- usar `confidence` como regra de decisao.

`classification.py`, `retrieval.py` e `index.py` permanecem protegidos. Qualquer alteracao neles exige antes um teste bloqueante reproduzivel, causa tecnica, menor mudanca possivel e risco de regressao explicitado.

## Arquitetura escolhida

A arquitetura aprovada e uma maquina de estados deterministica sobre os motores existentes.

```text
TriageEngine
  -> classify_ticket existente
  -> TriageState pequeno
  -> regras deterministicas de merge e contexto faltante
  -> perguntas fixas e limitadas
  -> KnowledgeEngine da Fase 4
```

A triagem nao possui retrieval proprio, nao possui prompt proprio de classificacao e nao acessa arquivos privados do indice de knowledge.

## Extensao estritamente aditiva do KnowledgeEngine

O contrato publico atual permanece valido e com o mesmo comportamento:

```text
KnowledgeEngine.search(text)
```

A Fase 5 adiciona:

```text
KnowledgeEngine.search_classified(text, classification)
```

A implementacao esperada e:

```text
search(text)
-> classify_ticket(text, client.chat)
-> search_classified(text, classification)
```

`search_classified()` executa os mesmos gates, embedding, threshold e retorno da Fase 4, apenas recebendo uma `TicketClassification` ja resolvida pela triagem para evitar uma segunda classificacao.

Regras obrigatorias:

- `search(text)` continua publico;
- nenhum caller existente precisa mudar;
- nenhuma reason, status, threshold ou semantica da Fase 4 pode mudar como efeito colateral;
- testes com os mesmos control doubles devem provar equivalencia entre `search(text)` e `classify_ticket + search_classified(text, classification)` para a mesma classificacao;
- os testes existentes da Fase 4 devem continuar passando sem mudanca de expectativa.

## Interface neutra de disponibilidade de knowledge

`TriageEngine` nao pode abrir `documents.jsonl`, matriz de embeddings, `manifest.json`, provenance ou `KnowledgeEngine.df` diretamente.

A interface aprovada e:

```text
KnowledgeEngine.available_systems(intent) -> tuple[str, ...]
```

Contrato:

- o resultado e derivado internamente somente dos documentos `APPROVED` ja carregados e validados pelo `KnowledgeEngine`;
- valores sao unicos e ordenados deterministicamente;
- `""` representa knowledge generica para o intent;
- `()` significa que nao existe artigo `APPROVED` para o intent;
- a triagem recebe somente metadado de disponibilidade, nunca texto de artigo, answer, documentos ou vetores.

Regras derivadas:

```text
available_systems(intent) == ()
-> TRIAGE_ABSTAINED / NO_APPROVED_KNOWLEDGE_FOR_INTENT
-> nao perguntar system

"" in available_systems(intent)
-> ausencia de system nao bloqueia a busca

available_systems(intent) contem apenas sistemas nao vazios
-> system e obrigatorio antes da busca
```

A existencia de knowledge generica relaxa somente a ausencia de system. Ela nao autoriza ignorar um system explicitamente ambiguo ou desconhecido fornecido pelo usuario.

Se o usuario informar um sistema conhecido que nao possui knowledge para aquele intent, a triagem nao deve induzi-lo a escolher outro sistema. Com contexto suficiente, a busca segue para a Fase 4 e pode terminar em `SYSTEM_MISMATCH`.

Um sistema literal nao presente em `SYSTEM_ALIASES` mas presente em `available_systems(intent)` e considerado coberto por knowledge para aquele intent. O parser especial de correcao continua restrito a aliases canonicos conhecidos.

## Estado da triagem

O estado e serializavel, pequeno e versionado.

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

`session_id` e opaco. Nao carrega nome, email, usuario, matricula ou identidade corporativa.

`turn_count` conta mensagens do usuario efetivamente processadas.

`clarification_count` conta perguntas emitidas pela triagem.

`problem_text` guarda somente a descricao substantiva atual do problema. Nao guarda transcript.

`intent`, `system`, `entities` e `confidence` representam o contexto resolvido atual. `confidence` e apenas metadado e nunca participa de gates.

`pending_field` indica qual slot a pergunta anterior tentou resolver.

`asked_fields` impede repetir a mesma pergunta no mesmo contexto do problema.

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

A implementacao vincula o `TriageEngine` a um `session_id` opaco fornecido pelo caller. `step(state, message)` rejeita um estado cujo `state.session_id` seja diferente do `session_id` ao qual aquele engine esta vinculado.

O caller sera responsavel futuramente por persistir e recuperar o estado correto. A Fase 5 nao implementa essa persistencia.

Estados `ANSWERED` e `ABSTAINED` sao terminais. Chamar `step()` novamente sobre estado terminal falha explicitamente e nunca reabre a mesma triagem.

## Classificacao por turno

Cada mensagem do usuario pode ser classificada no maximo uma vez com `classify_ticket`.

A triagem nao cria outro classificador e nao executa uma segunda classificacao ao entrar na knowledge.

O merge do resultado depende do estado e das regras abaixo.

## Tipos deterministas de mensagem para o merge

Antes das regras de merge, a mensagem e enquadrada em uma destas categorias. Essa etapa nao usa outro LLM.

### Correcao explicita de system

Reconhecida somente pelo parser conservador definido nesta spec. Quando reconhecida, tem precedencia sobre a contagem simples de sistemas explicitos.

### Resposta curta de system

Existe somente quando `pending_field == "system"` e uma das condicoes abaixo e verdadeira:

1. o texto normalizado e exatamente um alias ou nome canonico conhecido;
2. o texto normalizado e exatamente o mesmo system literal nao vazio retornado pela unica classificacao daquele turno;
3. o texto segue a forma curta `sistema <literal>` e a classificacao preserva exatamente esse literal;
4. a mensagem e uma correcao explicita aceita.

Uma resposta curta de system continua sendo slot-only mesmo quando o literal e desconhecido. Nesse caso ela nao substitui `problem_text` nem `intent`; ela conduz a `UNKNOWN_SYSTEM` conforme as regras de transicao.

### Nova descricao substantiva

Qualquer mensagem nao vazia que nao seja uma correcao explicita slot-only nem uma resposta curta de system e tratada como nova descricao substantiva.

Isso torna o merge testavel sem um segundo classificador ou parser generico de linguagem natural.

## Regras formais de merge do estado

As regras possuem precedencia na ordem abaixo.

### Regra 1. Estado terminal

Se `state.status` for `ANSWERED` ou `ABSTAINED`, a mensagem nao e processada. `step()` falha explicitamente.

### Regra 2. Correcao explicita de system

Uma correcao aceita atualiza somente `system`.

Ela preserva:

- `problem_text`;
- `intent`;
- `entities`;
- `confidence`.

Ela limpa `pending_field` quando esse campo for `system`.

A correcao nunca e reinterpretada como nova descricao substantiva, mesmo contendo dois nomes de sistema.

### Regra 3. Resposta curta ao `pending_field = system`

Uma resposta curta atualiza somente o candidato a `system`.

Ela nao substitui:

- `problem_text`;
- `intent`;
- `entities`;
- `confidence` da descricao substantiva anterior.

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

Uma palavra isolada nunca transforma o intent anterior em `OUTRO` apenas por causa da classificacao daquele turno.

Se a resposta curta continuar desconhecida ou ambigua, o contexto substantivo anterior permanece intacto e as regras de `UNKNOWN_SYSTEM` ou `AMBIGUOUS_SYSTEM` decidem se ainda cabe pergunta ou se a triagem deve terminar.

### Regra 4. Resposta ao `pending_field = problem`

A mensagem e tratada como nova descricao substantiva e recebe nova classificacao.

Ela substitui:

- `problem_text`;
- `intent`;
- `entities` integralmente;
- `confidence`.

`system` segue as regras de evidencia da nova descricao:

- sistema explicito unico substitui o anterior;
- multiplos sistemas sem correcao unica limpam `system`;
- correcao explicita ja teria sido tratada pela Regra 2;
- ausencia de nova evidencia de system preserva um system anteriormente resolvido.

Se a nova classificacao continuar com `intent == OUTRO`, o marcador `problem` permanece em `asked_fields` durante a decisao e o resultado e terminal `TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM`. A mesma pergunta nao pode ser emitida novamente.

Se a nova classificacao produzir intent utilizavel, ela estabelece um novo contexto substantivo: `pending_field` e limpo e `asked_fields` pode ser reiniciado para esse novo contexto. `turn_count` e `clarification_count` nunca reiniciam.

### Regra 5. Nova descricao substantiva fora de `pending_field = problem`

A nova descricao substitui o contexto substantivo atual.

Ao substituir `problem_text`:

- `problem_text` recebe somente a nova mensagem;
- `intent` e substituido pelo novo intent, inclusive se mudar;
- `entities` antigas sao descartadas integralmente;
- `entities` passam a ser somente as extraidas da nova descricao;
- `confidence` e substituida;
- `pending_field` e limpo;
- `asked_fields` e limpo para o novo contexto do problema;
- `turn_count` e `clarification_count` sao preservados;
- `system` e substituido se houver sistema explicito unico;
- `system` e limpo se houver mais de um sistema explicito sem correcao unica;
- se nao houver nova evidencia de system, o system anterior e preservado.

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

### Regra 6. Novo system explicito unico

Quando uma descricao substantiva trouxer exatamente um system explicito unico, ele substitui `state.system`.

### Regra 7. Multiplos systems explicitos

Se a mensagem trouxer mais de um system explicito e nao corresponder ao parser conservador de correcao, `system` e limpo e o resultado trata `AMBIGUOUS_SYSTEM`.

Nunca se escolhe automaticamente o primeiro, o ultimo ou o sistema que possui maior score de knowledge.

### Regra 8. Mudanca de intent

Mudanca de intent ocorre somente por nova descricao substantiva. Resposta curta de system e correcao explicita preservam o intent anterior.

Quando o intent muda por nova descricao substantiva, entities antigas sao descartadas e `available_systems(intent)` e recalculado para o novo intent.

## Parser conservador de correcao de system

O parser nao e um parser generico de linguagem natural.

Ele aceita somente uma estrutura inequivoca equivalente a:

```text
nao e <SYSTEM_A>, e <SYSTEM_B>
```

Requisitos cumulativos:

- `<SYSTEM_A>` e `<SYSTEM_B>` mapeiam de forma unica para aliases canonicos presentes em `SYSTEM_ALIASES`;
- os dois sistemas sao diferentes;
- existe exatamente um sistema negado e exatamente um afirmado;
- a estrutura de negacao e afirmacao e reconhecida deterministicamente;
- nenhum terceiro sistema explicito esta presente.

Quando aceito, `SYSTEM_B` substitui o system anterior.

Quando qualquer requisito falha, nao ha inferencia. `CIGAM e SIAGRI` continua `AMBIGUOUS_SYSTEM`.

O parser nao interpreta frases vagas, preferencias, contexto temporal, sinonimos livres ou intencao implicita.

## Deteccao do que falta e ordem de decisao

`missing_fields` nao e persistido. E derivado a cada turno.

A ordem de decisao, apos o merge, e:

1. validar estado terminal e limites;
2. tratar `intent == OUTRO`;
3. consultar `available_systems(intent)`;
4. se nao houver knowledge APPROVED para o intent, abster sem perguntar system;
5. tratar system explicitamente ambiguo ou desconhecido;
6. decidir se ausencia de system exige pergunta;
7. quando o contexto estiver suficiente, chamar knowledge retrieval.

Essa ordem impede pergunta inutil quando nao existe knowledge para o intent e impede que knowledge generica esconda um system ambiguo ou desconhecido que o usuario forneceu explicitamente.

### Problema insuficiente

`intent == OUTRO` e tratado como problema ainda nao suficientemente determinado para busca oficial.

Se `problem` ainda nao foi perguntado no contexto atual e os limites permitem:

```text
NEEDS_CLARIFICATION / MISSING_PROBLEM
question = "O que esta acontecendo?"
```

Se `problem` ja foi perguntado e a nova descricao continua `OUTRO`:

```text
TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM
```

`confidence` nunca altera essa decisao.

### Nenhuma knowledge APPROVED para o intent

Se `available_systems(intent) == ()`:

```text
TRIAGE_ABSTAINED / NO_APPROVED_KNOWLEDGE_FOR_INTENT
```

Nenhuma pergunta sobre system e emitida.

### System ambiguo

Multiplos systems explicitos, sem correcao inequivoca, resultam inicialmente em:

```text
NEEDS_CLARIFICATION / AMBIGUOUS_SYSTEM
```

se `system` ainda puder ser perguntado dentro dos limites.

Se `system` ja foi perguntado no mesmo contexto e a ambiguidade permanecer:

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

A pergunta solicita correcao objetiva sem sugerir qual sistema escolher.

Se o usuario ja teve uma oportunidade de corrigir `system` no mesmo contexto e continua fornecendo system desconhecido:

```text
TRIAGE_ABSTAINED / UNKNOWN_SYSTEM
```

### Knowledge generica

Se `""` estiver em `available_systems(intent)` e nao houver ambiguidade nem system desconhecido explicitamente fornecido, ausencia de system nao bloqueia a busca.

### Knowledge somente por system especifico

Se houver artigos `APPROVED` para o intent e todos tiverem `system != ""`, system e obrigatorio.

Se `state.system == ""`:

```text
NEEDS_CLARIFICATION / MISSING_SYSTEM
question = "Qual sistema esta com o problema?"
```

### System conhecido sem cobertura para o intent

Se o usuario forneceu system conhecido, mas ele nao aparece na disponibilidade daquele intent, a triagem nao pede outro system. O contexto e considerado claro o bastante para o gate da Fase 4, que pode retornar `SYSTEM_MISMATCH`.

## Limites de conversa

Constantes aprovadas:

```text
MAX_USER_TURNS = 3
MAX_CLARIFICATIONS = 2
```

Semantica precisa:

- uma mensagem e aceita quando `turn_count < MAX_USER_TURNS` antes do processamento;
- a mensagem aceita incrementa `turn_count` e e processada integralmente;
- o terceiro turno pode resultar em `KNOWLEDGE_FOUND`;
- um quarto turno e rejeitado antes de classificacao ou merge;
- se, apos processar o terceiro turno, ainda seria necessario emitir nova pergunta, a triagem termina em `TRIAGE_ABSTAINED / MAX_TURNS` em vez de emitir pergunta que exigiria quarto turno;
- uma nova pergunta so pode ser emitida quando `clarification_count < MAX_CLARIFICATIONS`;
- ao emitir pergunta, `clarification_count` e incrementado;
- se seria necessaria uma terceira pergunta, termina em `TRIAGE_ABSTAINED / MAX_CLARIFICATIONS`;
- cada campo pode ser perguntado no maximo uma vez dentro do mesmo contexto substantivo;
- uma resposta que nao resolve o campo perguntado nao apaga o marcador desse campo;
- uma nova descricao substantiva utilizavel pode iniciar novo contexto e limpar `asked_fields`, mas nunca reinicia os dois contadores globais.

Cenario obrigatorio:

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
- o system resolvido que tambem veio da conversa, quando necessario para refletir esclarecimento ou correcao posterior.

A triagem nao pode adicionar:

- labels de intent como `PROBLEMA_ACESSO`;
- tags de knowledge;
- sinonimos artificiais;
- termos extras sugeridos pelo classificador;
- frases de reforco semantico;
- title ou answer de artigos;
- texto historico.

### Reconciliacao lexical de system

Quando `problem_text` ja contem exatamente o system resolvido, ele e usado sem duplicar system.

Quando `problem_text` nao contem system explicito e o system foi obtido em resposta curta, o system pode ser acrescentado uma unica vez como contexto literal separado.

Quando `problem_text` contem aliases antigos ou multiplos que foram posteriormente corrigidos ou desambiguados pelo usuario, a query builder pode somente remover spans exatos reconhecidos pelos aliases existentes que conflitam com o system final e acrescentar o system final resolvido. Todo o restante do texto deve ser preservado, salvo normalizacao de espaco causada pela remocao lexical.

Essa reconciliacao existe apenas para honrar correcao ou desambiguacao explicita do usuario. Ela nao pode reescrever o problema, adicionar sinonimos, adicionar intent textual ou inserir termos destinados a aumentar similaridade.

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
- nao existe ambiguidade ou system desconhecido pendente;
- os limites nao exigem abstencao antes da busca.

A Fase 5 constroi uma `TicketClassification` a partir do estado resolvido e chama:

```text
KnowledgeEngine.search_classified(query_text, classification)
```

O threshold continua pertencendo ao `KnowledgeEngine` e permanece `0.65`. A triagem nao possui threshold alternativo.

Se a Fase 4 retornar `KNOWLEDGE_FOUND`, a Fase 5 termina em estado interno `ANSWERED` e devolve o answer literal aprovado.

Se a Fase 4 retornar `NO_APPROVED_KNOWLEDGE`, a Fase 5 nao inventa procedimento e termina em estado interno `ABSTAINED`. Quando a causa vier do retrieval da Fase 4, a reason original e preservada, por exemplo:

- `SYSTEM_MISMATCH`;
- `INTENT_MISMATCH`;
- `BELOW_THRESHOLD`;
- `UNKNOWN_SYSTEM`;
- `CONTEXTO_AMBIGUO`, se ainda alcancavel como defesa em profundidade.

## Contrato publico de resultado

Existem exatamente tres `status` publicos.

### `NEEDS_CLARIFICATION`

Semantica: existe uma unica pergunta objetiva permitida que ainda pode tornar o contexto suficiente.

```text
status = NEEDS_CLARIFICATION
reason = MISSING_PROBLEM | MISSING_SYSTEM | AMBIGUOUS_SYSTEM | UNKNOWN_SYSTEM
question = texto fixo e objetivo
knowledge = null
```

### `KNOWLEDGE_FOUND`

Semantica: a Fase 4 encontrou artigo `APPROVED` pelos mesmos gates e threshold existentes.

```text
status = KNOWLEDGE_FOUND
reason = MATCH
question = null
knowledge = objeto publico da Fase 4
```

O `answer` e literal e nunca e persistido no `TriageState`.

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

Reasons originadas na Fase 4 sao preservadas quando o retrieval ja tiver sido chamado.

Nenhum resultado publico inclui transcript completo, historico de ticket, `ticket_id` historico, embeddings ou cadeia de raciocinio.

## Smoke cases obrigatorios

Todas as conversas e fixtures sao 100% sinteticas.

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

Nenhum estado de B influencia A.

### 10. Anti-loop

```text
U: Preciso de ajuda.
=> NEEDS_CLARIFICATION / MISSING_PROBLEM
U: Nao sei explicar.
=> TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM
```

A mesma pergunta nao e repetida.

## Testes unitarios obrigatorios alem do smoke

Os testes cobrem pelo menos:

- equivalencia retrocompativel de `search()` e `search_classified()`;
- `available_systems(intent)` sem expor internals;
- nenhum artigo para intent evita pergunta inutil de system;
- knowledge generica nao exige system ausente;
- system ambiguo/desconhecido explicito nao e ignorado por knowledge generica;
- knowledge somente especifica exige system;
- resposta curta de system preserva intent, problem_text, entities e confidence anteriores;
- resposta curta desconhecida nao vira nova descricao substantiva;
- correcao explicita preserva intent e entities;
- nova descricao substantiva substitui problem_text;
- nova descricao substantiva remove entities antigas;
- mudanca de intent recalcula disponibilidade;
- novo system explicito substitui anterior;
- multiplos systems sem correcao ficam ambiguos;
- parser de correcao aceita apenas o padrao conservador aprovado;
- parser rejeita terceiro system, aliases desconhecidos e frases vagas;
- resposta ainda vaga a `MISSING_PROBLEM` nao repete a pergunta;
- terceiro turno pode resolver e retornar `KNOWLEDGE_FOUND`;
- quarto turno e rejeitado antes de classificacao;
- terceira pergunta nunca e emitida;
- campo nao e perguntado duas vezes no mesmo contexto;
- `confidence` nao altera nenhuma transicao;
- query nao contem label artificial de intent;
- reconciliacao lexical de system nao acrescenta termos alem do system corrigido;
- fluxo single-turn e fluxo two-turn chegam a mesma knowledge esperada;
- threshold permanece `0.65`;
- session mismatch e rejeitado;
- `ANSWERED` e `ABSTAINED` sao terminais;
- estado nao contem answer;
- resultado publico nao contem transcript;
- nenhum `ticket_id` historico aparece.

## Privacidade e dados de teste

Nenhuma conversa real, ticket real, identificador pessoal, texto corporativo, report com conteudo corporativo, indice real ou embedding real entra no Git.

O smoke pode persistir apenas metadados agregados seguros:

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

O report nao persiste mensagens, transcript nem `answer`.

## Arquivos previstos para implementacao

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

`src/ai_service_desk/engine/knowledge.py` tambem nao precisa ser alterado no desenho atual. A disponibilidade e exposta por `KnowledgeEngine`, que ja carrega somente indice de knowledge com provenance fail-closed.

## Workflow de homologacao

A Fase 5 possui workflow manual para o Dell homologado, seguindo o padrao das fases anteriores:

- `workflow_dispatch`;
- runner `self-hosted`, `Windows`, `X64`, `ai-service-desk`, `ollama`;
- Python 3.14;
- Ollama somente em loopback;
- knowledge sintetica da Fase 4;
- conversas sinteticas da Fase 5;
- sem `upload-artifact`;
- sem imprimir transcript ou answer;
- report apenas agregado e local.

## Invariantes de homologacao

Antes de considerar a Fase 5 homologada:

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

Mitigacao: `MAX_USER_TURNS = 3`, `MAX_CLARIFICATIONS = 2`, `asked_fields`, regra especial para resposta vaga a `MISSING_PROBLEM` e estados terminais.

### Contexto obsoleto

Risco: entities ou intent de problema antigo sobreviverem a nova descricao.

Mitigacao: substituicao atomica de `problem_text`, intent, entities e confidence em nova descricao substantiva; system segue regras explicitas de evidencia.

### Correcao interpretada como nova intencao

Risco: `nao e CIGAM, e SIAGRI` alterar intent ou entities.

Mitigacao: parser de correcao tem precedencia e atualiza somente `system`.

### Manipulacao da query para aumentar score

Risco: adicionar labels ou termos artificiais para superar `0.65`.

Mitigacao: query limitada a texto real do problema e system real fornecido na conversa, com apenas reconciliacao lexical deterministica de aliases conflitantes apos correcao ou desambiguacao explicita.

## Criterios de aceite da implementacao

A Fase 5 estara pronta para homologacao quando:

1. `KnowledgeEngine.search()` continuar retrocompativel;
2. `search_classified()` evitar segunda classificacao sem duplicar retrieval;
3. `available_systems()` encapsular disponibilidade sem expor internals;
4. a maquina de estados obedecer integralmente as regras de merge desta spec;
5. os tres estados publicos tiverem transicoes deterministicas;
6. os 10 smoke cases forem cobertos;
7. os limites de 3 turnos e 2 esclarecimentos forem respeitados sem impedir resolucao no terceiro turno;
8. nenhuma query receber labels artificiais ou alteracao de threshold;
9. todas as invariantes de privacidade e isolamento forem verificadas;
10. os 177 testes existentes continuarem verdes e os novos testes passarem.
