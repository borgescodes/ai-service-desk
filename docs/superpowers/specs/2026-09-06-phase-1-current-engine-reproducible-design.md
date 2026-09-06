# Fase 1: Motor atual reproduzível

Status: desenho aprovado em conversa em 2026-09-06. Documento materializado para revisão antes do plano de implementação.

## Objetivo

Migrar o motor local 2.1 para o pacote oficial `ai_service_desk`, preservando seus contratos observáveis de classificação, segurança, indexação, recuperação e abstinência, sem antecipar o uso do corpus corporativo real ou a calibração de qualidade das fases seguintes.

A Fase 1 transforma o motor existente em uma parte nativa, reproduzível e testável do repositório oficial.

O norte do produto permanece:

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

## Contexto e baseline

A implementação de referência é o pacote legado `motor_ai_service_desk_v2_1.zip`. Ele já contém classificação local, preparação de dados, cliente Ollama restrito a loopback, índice NumPy com checkpoint e proveniência, recuperação por similaridade, regras de contexto, abstinência e CLI.

A suíte legado possui 75 testes coletados e passou novamente no ambiente isolado usado durante o desenho desta fase. Esse resultado é baseline de comportamento, não evidência da migração futura e não estabelece uma meta numérica de testes para o novo pacote.

A Fase 0 já estabeleceu:

- pacote Python oficial em layout `src/`;
- Python 3.14 como versão oficial;
- `pyproject.toml`, `pip` e `.venv`;
- `pytest` e Ruff como gates;
- CI determinístico hospedado pelo GitHub;
- homologação local separada no runner Windows com Ollama;
- política de dados, segredos e artefatos gerados;
- integração somente por pull request.

A Fase 1 deve estender essa fundação. Não deve criar uma segunda arquitetura paralela.

## Decisão arquitetural aprovada

A abordagem escolhida é incorporar o comportamento do motor 2.1 ao pacote oficial.

Não manter `motor-local` como aplicação paralela e não reescrever o produto do zero.

O ZIP legado é fonte de migração e referência histórica. Código de produção da Fase 1 não pode depender do ZIP, de caminhos externos ao repositório ou de imports legados como `classificar_ticket`, `busca_core` ou `app.*`.

A compatibilidade exigida é comportamental. Compatibilidade de imports Python legados não é requisito.

## Estrutura alvo

A estrutura proposta é:

```text
src/ai_service_desk/
├── __init__.py
├── __main__.py
├── cli.py
└── engine/
    ├── __init__.py
    ├── classification.py
    ├── data.py
    ├── index.py
    ├── ollama.py
    ├── retrieval.py
    ├── types.py
    └── validation.py

tests/
├── fixtures/
├── test_cli.py
└── engine/
    ├── test_classification.py
    ├── test_data.py
    ├── test_index.py
    ├── test_ollama.py
    ├── test_retrieval.py
    └── test_validation.py

docs/
└── migration/
    └── engine-v2.1-equivalence.md

.github/
└── workflows/
    └── engine-smoke.yml
```

Esse desenho é um alvo de responsabilidade, não uma obrigação de criar arquivos vazios. Módulos pequenos podem ser combinados quando isso mantiver uma responsabilidade única e clara.

## Escopo funcional

### Incluído

A Fase 1 migra e preserva:

- classificação conservadora da solicitação;
- grounding de sistemas explicitamente citados;
- preservação de rotina e filial quando aparecem literalmente;
- tratamento seguro de múltiplos sistemas explícitos;
- preparação e sanitização de dados;
- validação de corpus;
- cliente Ollama somente local;
- embeddings locais;
- criação de índice com manifesto;
- checkpoint e retomada por lotes;
- escrita atômica de estado;
- hashes e proveniência;
- validação de modelo, digest e dimensão;
- importação controlada de índice legado por sentinelas;
- recuperação por similaridade;
- restrição por contexto classificado;
- filtro de conteúdo sensível;
- threshold legado;
- abstinência;
- CLI operacional;
- validação integrada em ambiente local;
- testes de regressão dos contratos relevantes.

### Fora de escopo

A Fase 1 não inclui:

- corpus corporativo real versionado no Git;
- base preparada real como fixture;
- índice corporativo real;
- embeddings corporativos reais;
- calibração do threshold `0.65`;
- medição de precisão, recall, acurácia ou cobertura do retrieval;
- geração de resposta técnica ao usuário;
- RAG;
- FAQ;
- memória de conversa;
- playbooks;
- policy engine;
- execução de ações;
- API web;
- banco de dados;
- frontend;
- framework genérico de agentes;
- abstração genérica de provedores de IA.

O retrieval sobre o corpus TI real permanece reservado para a Fase 2. Avaliação e calibração permanecem reservadas para a Fase 3.

## Dependências

A Fase 1 adiciona somente as dependências de runtime já necessárias ao motor legado:

```text
numpy>=2.0,<3
pandas>=2.2,<4
requests>=2.32,<3
```

As dependências de desenvolvimento continuam contendo pytest e Ruff.

Não introduzir nesta fase FastAPI, Pydantic, LangChain, LlamaIndex, ChromaDB, FAISS, SQLAlchemy, SDK de provedor externo ou framework de agentes.

`requirements.txt`, `setup.ps1` e `run_tests.py` não serão mecanismos oficiais no pacote novo. Dependências ficam em `pyproject.toml`, testes rodam por pytest e a operação oficial parte do módulo Python.

## Contrato de classificação

O contrato conceitual permanece:

```text
TicketClassification
├── intent
├── system
├── entities
└── confidence
```

A implementação pode usar `dataclass` ou estrutura equivalente da biblioteca padrão. Não é necessário adicionar biblioteca de validação de modelos.

### Intents permitidas

A lista fechada do motor legado deve ser preservada sem expansão nesta fase:

```text
LIBERACAO_ROTINA
PROBLEMA_ACESSO
ERRO_SISTEMA
INSTALACAO_SOFTWARE
PROBLEMA_IMPRESSAO
PROBLEMA_REDE
ORIENTACAO
OUTRO
```

### Sistemas conhecidos

Os sistemas e aliases já reconhecidos pelo legado devem ser migrados e cobertos por teste. Não ampliar o catálogo nesta fase sem uma necessidade de equivalência identificada durante a migração.

Os nomes canônicos atuais são:

```text
CIGAM
SIAGRI
OUTLOOK
TEAMS
OFFICE 365
WHATSAPP
WINDOWS
```

### Invariantes

Preservar os seguintes comportamentos:

- entrada deve ser string não vazia;
- consulta de classificação aceita no máximo 3000 caracteres;
- `think=false`;
- `stream=false`;
- temperatura zero;
- resposta estruturada em JSON;
- somente as quatro chaves do contrato são aceitas;
- `intent` precisa pertencer à lista fechada;
- `system` deve ser string curta;
- `entities` deve ser objeto pequeno de strings;
- `confidence` não aceita booleano, NaN ou infinito;
- `confidence` deve permanecer entre 0 e 1;
- sistema inventado pelo modelo não ganha autoridade;
- sistema explicitamente mencionado pelo usuário é preservado;
- múltiplos sistemas explícitos tornam o contexto ambíguo;
- termos genéricos como `sistema`, `rede`, `internet`, `impressora`, `computador`, `erp`, `software`, `aplicativo` e `notebook` não são promovidos automaticamente a sistema corporativo;
- rotina e filial são extraídas somente de evidência literal;
- identificadores extraídos nunca autorizam ação.

Exemplo obrigatório de grounding:

```text
Entrada: preciso liberar a rotina 001024 no CIGAM
Resposta hipotética do modelo: system=SAP, rotina=123
Resultado oficial: system=CIGAM, rotina=001024
```

O modelo auxilia a classificação. Evidência literal do usuário tem precedência.

## Cliente Ollama e embeddings

O cliente Ollama continua sendo uma implementação local específica para desenvolvimento e homologação.

### Regra de rede

Somente HTTP em loopback é permitido:

```text
localhost
127.0.0.1
::1
```

Rejeitar:

- host remoto;
- HTTPS externo;
- usuário ou senha embutidos na URL;
- query string ou fragmento na URL base;
- caminhos base diferentes de vazio ou `/`;
- endpoints fora de `/api/`;
- redirects HTTP;
- proxies herdados do ambiente;
- modelos marcados como remotos ou cloud.

A sessão HTTP deve continuar com confiança no ambiente desativada, equivalente a `trust_env=False`, e redirects desativados.

Nenhum modelo é baixado automaticamente.

### Modelos da Fase 1

```text
Classificação: qwen3.5:4b
Embeddings: qwen3-embedding:0.6b
Dimensão esperada: 1024
```

O digest real do modelo é lido do Ollama e participa da proveniência do índice.

O embedder deve:

- exigir lista não vazia de textos não vazios;
- usar `truncate=false`;
- rejeitar embeddings com NaN, infinito ou norma zero;
- normalizar vetores;
- exigir quantidade de vetores e dimensão compatíveis com a entrada e o modelo.

## Preparação e sanitização de dados

A capacidade de preparar exports TiFlux permanece disponível, porém exports brutos e corpus corporativo preparado continuam fora do Git nesta fase.

A preparação deve preservar:

- leitura de tickets e apontamentos com IDs válidos;
- exclusão de tickets abertos ou cancelados;
- filtro opcional para escopo TI;
- remoção de apontamentos órfãos do conjunto preparado;
- exclusão de registros com termos sensíveis;
- remoção de mensagens genéricas sem conteúdo útil;
- ordenação cronológica de apontamentos quando houver coluna temporal;
- mascaramento de URL, email, IP, CPF, telefone e nomes conhecidos quando aplicável;
- limitação de `texto_busca` a 6000 caracteres;
- marcação `HISTORICO_NAO_VALIDADO`;
- relatório de preparação com contagens relevantes.

O mascaramento é parcial e não certifica anonimização. Qualquer histórico exibido continua exigindo revisão humana.

### Corpus para testes

Todos os testes da Fase 1 usam dados sintéticos.

Nenhuma linha do corpus corporativo real pode ser copiada para fixtures.

As fixtures sintéticas precisam cobrir pelo menos:

- CIGAM com rotina;
- SIAGRI;
- problema de impressão;
- problema de rede;
- consulta sem sistema;
- sistema sem histórico compatível;
- múltiplos sistemas explícitos;
- candidato acima do threshold;
- candidato abaixo do threshold;
- registro bloqueado por conteúdo sensível.

## Índice e proveniência

O índice oficial continua baseado em NumPy nesta fase.

### Receita

A receita legado deve ser preservada:

```text
texto_busca-plain-v1
```

Mudança de receita exige índice novo e não pode ser tratada como compatível silenciosamente.

### Manifesto

O manifesto deve registrar no mínimo:

```text
version
source_hash
rows
dimensions
model
model_digest
recipe
completed
complete
batches
matrix_hash
legacy_import
```

Para importação legado, registrar também as sentinelas e uma nota explícita de que três sentinelas não provam a proveniência de todos os vetores históricos.

### Regras de consistência

Preservar:

- `ticket_id` obrigatório, não vazio e único;
- `texto_busca` obrigatório e não vazio;
- batch de indexação entre 1 e 100;
- lock de indexação para evitar duas gravações concorrentes;
- documentos gravados com hash do conteúdo normalizado do corpus;
- matriz `float32`;
- vetores normalizados;
- hash por batch confirmado;
- checkpoint atualizado somente após batch válido;
- retomada sem repetir batch já confirmado;
- `complete=true` somente após finalizar todas as linhas;
- hash final da matriz;
- leitura recusada quando o índice estiver incompleto;
- leitura recusada quando documentos ou matriz tiverem sido alterados;
- leitura recusada para receita incompatível;
- leitura recusada quando linhas e matriz estiverem desalinhadas;
- busca recusada quando modelo, digest ou dimensão do embedder não coincidirem com o manifesto.

Índice incompatível ou corrompido é erro operacional. Não existe fallback silencioso.

### Importação de índice legado

`import-legacy` é preservado como capacidade de migração.

A importação deve ocorrer em diretório novo e nunca sobrescrever a origem.

A matriz legado é normalizada e validada estruturalmente. Três posições sentinela, primeira, intermediária e última, são recalculadas com o modelo atual e precisam ter similaridade mínima equivalente ao contrato legado antes da importação ser aceita.

Essa verificação é uma sentinela de compatibilidade, não certificação de todos os vetores históricos.

## Contrato de retrieval

`RetrievalEngine.search(text)` é o contrato principal do motor.

O resultado estruturado deve continuar expondo dados equivalentes a:

```text
status
classification
threshold
context_mode
pool_size
total_documents
best_score
candidates
warnings
timings
```

### Estados de domínio

Preservar:

```text
ENCONTRADOS
SEM_EVIDENCIA
SEM_CONTEXTO
CONTEXTO_AMBIGUO
```

`SEM_EVIDENCIA`, `SEM_CONTEXTO` e `CONTEXTO_AMBIGUO` são resultados de domínio. Não são falhas técnicas.

### Parâmetros legado

Preservar como comportamento inicial:

```text
threshold padrão: 0.65
top_k padrão: 5
min_matches padrão: 3
```

O threshold aceito pelo núcleo deve ser finito e estar entre `-1` e `1`. `top_k` deve permanecer entre 1 e 20.

O valor `0.65` é reproduzido, não validado como ótimo. Sua calibração pertence à Fase 3.

### Fluxo

```text
texto do usuário
↓
validação de entrada
↓
classificação local
↓
grounding de evidências literais
↓
embedding da consulta
↓
validação de compatibilidade do índice
↓
seleção do pool por contexto
↓
filtro de segurança
↓
similaridade
↓
threshold legado
↓
resultado estruturado
```

### Regra de contexto

Se houver mais de um sistema explícito no texto, retornar `CONTEXTO_AMBIGUO` e nenhum histórico deve ser apresentado como procedimento.

Se existir exatamente um sistema explícito, somente registros compatíveis com esse sistema podem ser promovidos como candidatos.

A busca pode ampliar internamente a procura por registros compatíveis com o mesmo sistema quando o primeiro pool estiver escasso. Nunca pode completar resultados com outro sistema.

Se nenhum registro compatível com o sistema explícito existir, retornar `SEM_CONTEXTO`.

Quando o pool compatível tiver menos que `min_matches`, adicionar aviso de contexto escasso, mas não usar outro sistema para completar resultados.

### Segurança dos candidatos

Antes da promoção por score, excluir candidatos com termos sensíveis nos campos pesquisados.

Cada candidato deve permanecer marcado como:

```text
HISTORICO_NAO_VALIDADO
```

Nenhum candidato é chamado de solução, procedimento aprovado ou autorização.

Campos textuais exibidos devem passar por sanitização.

### Abstinência

A ausência de evidência suficiente é um resultado válido.

Se nenhum candidato seguro no contexto atingir o threshold:

```text
status = SEM_EVIDENCIA
candidates = []
```

Não reduzir o threshold automaticamente, não completar resultados com outro sistema e não pedir ao LLM para inventar uma solução.

## CLI oficial

O ponto de entrada oficial passa a ser:

```powershell
python -m ai_service_desk <command>
```

Os comandos conceituais são:

```text
doctor
inspect
show-index
prepare
index
import-legacy
search
validate
```

O CLI não contém regra de negócio. Ele valida argumentos, chama o motor e apresenta resultado.

Comandos que dependem de corpus ou índice devem aceitar caminhos explícitos. O pacote de produção não pode depender de arquivos corporativos dentro de `src/`, nem de caminhos externos fixos.

### Comportamentos operacionais

Preservar:

- `doctor` verifica Ollama e presença dos dois modelos sem baixar nada;
- `inspect` informa metadados do corpus sem imprimir históricos;
- `show-index` expõe somente metadados seguros do manifesto;
- `prepare` recusa sobrescrever saída existente por padrão;
- `index` mostra progresso e permite retomada;
- `import-legacy` trabalha em destino novo;
- `search` suporta consulta única e modo interativo sem memória entre atendimentos;
- armazenamento de contexto em JSON é opcional e explícito;
- gravação de contexto exige consulta única para evitar armazenamento acidental de conversas;
- `validate` gera relatório estruturado e deixa explícito que validação funcional não equivale a acurácia ou aprovação de procedimentos;
- `KeyboardInterrupt` informa que batches confirmados podem ser retomados;
- erros operacionais retornam código diferente de zero sem imprimir o texto integral do chamado.

## Estratégia de migração

A migração ocorre por comportamento, não por arquivo.

Ordem recomendada:

```text
contratos e tipos
↓
validação e sanitização
↓
classificação e grounding
↓
cliente Ollama
↓
preparação de dados
↓
índice e manifesto
↓
retrieval
↓
CLI
↓
homologação integrada
```

Cada bloco entra com ciclo de teste falhando, implementação mínima e teste passando quando houver comportamento de produto.

Não copiar todo o legado para dentro de `src/` e corrigir depois.

## Equivalência com os 75 testes legados

Cada teste legado deve receber um destino documentado em:

```text
docs/migration/engine-v2.1-equivalence.md
```

Categorias permitidas:

```text
MIGRADO
SUBSTITUIDO_POR_TESTE_EQUIVALENTE
FORA_DE_ESCOPO
OBSOLETO_COM_JUSTIFICATIVA
```

Nenhum comportamento relevante pode desaparecer sem justificativa explícita.

A nova suíte não precisa ter exatamente 75 testes. O objetivo é preservar os contratos relevantes com testes claros no pacote oficial.

## Estratégia de testes

### CI determinístico

O CI hospedado não depende de Ollama, notebook Dell ou serviço externo.

Cobrir no mínimo:

- contrato de classificação;
- todos os intents permitidos e rejeição de intent inválida;
- preservação de sistema literal;
- remoção de sistema inventado;
- extração literal de rotina e filial;
- múltiplos sistemas explícitos;
- JSON inválido e tipos inválidos;
- confiança NaN, infinita, booleana ou fora do intervalo;
- URL Ollama inválida;
- proxy de ambiente ignorado;
- redirect bloqueado;
- modelo ausente, remoto ou sem digest;
- embeddings inválidos;
- dimensão de embedding incompatível;
- sanitização e termos sensíveis;
- corpus inválido;
- preparação sintética de dados;
- lock de índice;
- checkpoint e retomada;
- batch corrompido;
- índice incompleto;
- hash inconsistente;
- receita incompatível;
- modelo, digest e dimensão incompatíveis;
- importação legado com sentinelas sintéticas;
- ranking;
- pool por sistema;
- ausência de fallback entre sistemas;
- threshold;
- abstinência;
- candidatos `HISTORICO_NAO_VALIDADO`;
- estados `SEM_CONTEXTO` e `CONTEXTO_AMBIGUO`;
- comandos principais do CLI.

Chamadas Ollama no CI devem usar servidor HTTP controlado ou transporte de teste. O CI nunca chama `localhost:11434` real.

### Homologação real no Dell

Criar workflow manual separado:

```text
.github/workflows/engine-smoke.yml
```

Ele não substitui nem acumula responsabilidades em `.github/workflows/local-ai-smoke.yml`.

Responsabilidades:

```text
local-ai-smoke.yml
comprova runner, Python, Ollama e modelos

engine-smoke.yml
comprova o motor oficial usando essa infraestrutura
```

`engine-smoke.yml` deve usar o runner já homologado:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

O caminho real a provar é:

```text
CLI oficial
↓
classificação real com qwen3.5:4b
↓
embedding real com qwen3-embedding:0.6b
↓
índice sintético
↓
retrieval
↓
resultado estruturado
```

O workflow usa somente dados sintéticos versionados ou gerados durante o job.

Ele permanece manual via `workflow_dispatch` e não é gate automático de todo PR.

Quando for necessário executá-lo, manter a regra operacional da Fase 0: disparar ou identificar a execução, informar o que deve concluir e parar. O operador acompanha o GitHub e retorna com o resultado. Não fazer polling.

## Tratamento de falhas

Falhas técnicas devem ser explícitas e seguras.

Exemplos:

- entrada inválida;
- Ollama indisponível;
- timeout;
- modelo obrigatório ausente;
- modelo remoto;
- resposta JSON inválida;
- classificação truncada pelo limite de tokens;
- embedding inválido;
- corpus inválido;
- índice ausente;
- índice incompleto;
- índice corrompido;
- índice incompatível;
- checkpoint inválido;
- lock de indexação existente;
- destino de importação já ocupado.

Não incluir texto integral do chamado em mensagens de erro.

Estados de domínio como `SEM_EVIDENCIA`, `SEM_CONTEXTO` e `CONTEXTO_AMBIGUO` devem continuar sendo resultados estruturados, não exceções.

## Dados, privacidade e artefatos

### Permitido no Git

- código do motor;
- testes;
- fixtures sintéticas pequenas;
- documentação de equivalência;
- workflows sem credenciais.

### Fora do Git

- exports brutos do TiFlux;
- corpus corporativo preparado;
- embeddings corporativos;
- índices corporativos;
- checkpoints reais;
- logs;
- relatórios temporários;
- contexto de atendimentos reais.

Os diretórios de artefatos continuam seguindo a política da Fase 0, incluindo `artifacts/`, `embeddings/`, `logs/` e `reports/` fora do versionamento por padrão.

Nenhum segredo, token, cookie, senha ou credencial pode entrar no Git.

## Riscos e mitigação

### Mudança silenciosa de comportamento

Mitigação: migração por contratos e tabela de equivalência dos testes legados.

### Mistura entre Fase 1 e Fase 2

Mitigação: usar somente fixtures sintéticas e não medir retrieval no corpus real nesta fase.

### Acoplamento arquitetural permanente ao Ollama

Mitigação: isolar a comunicação em `engine/ollama.py`, sem introduzir agora uma hierarquia abstrata de providers. Ollama é a implementação concreta necessária nesta fase, não uma premissa permanente do produto web.

### Testes falsamente verdes

Mitigação: separar CI determinístico de homologação manual com modelos reais.

### Vazamento de dados

Mitigação: fixtures sintéticas, sanitização, filtro de termos sensíveis e nenhuma base real no Git.

### Reescrita excessiva

Mitigação: preservar contratos antes de melhorar arquitetura. Refatorações só entram quando necessárias para encaixar o motor no pacote oficial ou remover dependências da estrutura legado.

## Gates antes do pull request

Executar no ambiente Python 3.14:

```powershell
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m ai_service_desk doctor
```

`doctor` exige Ollama real. Quando o ambiente local de implementação não tiver Ollama disponível, esse gate deve ser executado na homologação manual e não deve ser falsificado ou substituído por bypass.

Os gates determinísticos obrigatórios antes do PR continuam sendo instalação, Ruff e pytest.

## Critérios mensuráveis de saída

A Fase 1 só pode ser considerada concluída quando houver evidência de que:

- `ai_service_desk` continua instalável com Python 3.14;
- o motor executa exclusivamente a partir do pacote oficial em `src/`;
- nenhum código de produção depende do ZIP legado ou de `motor-local`;
- os oito intents fechados estão preservados;
- classificação preserva sistema explicitamente citado pelo usuário;
- sistema inventado pelo modelo não é promovido;
- rotina e filial permanecem extrações literais;
- múltiplos sistemas explícitos produzem `CONTEXTO_AMBIGUO`;
- cliente Ollama rejeita hosts não locais;
- proxy de ambiente não é usado;
- redirects são bloqueados;
- modelos remotos são bloqueados;
- nenhum modelo é baixado automaticamente;
- embeddings inválidos são rejeitados;
- dimensão 1024 é exigida para `qwen3-embedding:0.6b`;
- corpus inválido é rejeitado;
- preparação de dados preserva sanitização e filtro de conteúdo sensível;
- índice registra modelo, digest, dimensão, linhas, receita e conclusão;
- checkpoint e retomada funcionam sem repetir batch confirmado;
- índice incompleto, corrompido ou incompatível é recusado;
- importação legado é validada com sentinelas e registra sua limitação de proveniência;
- retrieval respeita o contexto do sistema;
- não existe fallback de candidatos entre sistemas;
- threshold padrão `0.65` é reproduzido;
- ausência de evidência retorna `SEM_EVIDENCIA` com candidatos vazios;
- ausência de histórico compatível com sistema explícito retorna `SEM_CONTEXTO`;
- candidatos continuam marcados como `HISTORICO_NAO_VALIDADO`;
- nenhuma geração de solução técnica foi introduzida;
- todos os testes do novo pacote usam somente dados sintéticos;
- todos os 75 testes legados possuem destino documentado;
- `python -m ruff check .` passa;
- `python -m ruff format --check .` passa;
- `python -m pytest` passa no CI hospedado com Python 3.14;
- `engine-smoke.yml` passa manualmente no Dell com os dois modelos locais;
- `.github/workflows/local-ai-smoke.yml` permanece separado e sem mudança funcional não necessária;
- nenhum corpus corporativo, embedding real, segredo ou export bruto entra no Git;
- a mudança é revisada por pull request antes do merge.

## Definição operacional de sucesso

Em clone limpo, com Python 3.14:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

No Dell com Ollama disponível:

```text
engine-smoke.yml = success
```

A execução manual deve provar o motor oficial com classificação real, embedding real, índice sintético e retrieval estruturado.

## Regra de progressão

A Fase 2 só começa depois que todos os critérios mensuráveis desta especificação estiverem satisfeitos e a Fase 1 estiver integrada por pull request revisado.

Ter um motor funcional não autoriza usar o corpus real antecipadamente.
