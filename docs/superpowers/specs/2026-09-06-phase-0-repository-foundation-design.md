# Fase 0: Fundação do Repositório

Status: aprovado em 2026-09-06

## Objetivo

Estabelecer uma fundação simples, reproduzível e verificável para o AI Service Desk antes da migração do motor atual.

A Fase 0 não implementa lógica de negócio, retrieval, FAQ, playbooks, integrações, execução automática nem interface web. Seu papel é criar a base técnica e operacional que permitirá evoluir o produto em fases independentes e mensuráveis.

O norte do produto permanece:

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

## Princípios aprovados

- Um único repositório, backend primeiro.
- Pacote Python real desde o início, usando layout `src/`.
- Python 3.14 como versão oficial nesta fase.
- `pyproject.toml`, `pip` e `.venv` como base de dependências e ambiente.
- Fundação pura na Fase 0, sem migrar o motor atual.
- Desenvolvimento em branch curta com integração por pull request.
- CI determinístico em runner hospedado pelo GitHub.
- Homologação com Ollama em runner Windows self-hosted, somente por `workflow_dispatch`.
- `pytest` e `ruff` como gates de qualidade.
- Documentação em português, com código, pacotes, módulos, testes e identificadores técnicos em inglês.
- Exports brutos do TiFlux ficam fora do Git.
- Corpus real preparado para o motor pode ser versionado no repositório privado, mas somente a partir da Fase 1.
- Segredos, credenciais, tokens, cookies e chaves nunca entram no Git.
- Não fazer polling de GitHub Actions. O operador acompanha a execução e retorna com o resultado.
- Não afirmar conclusão ou sucesso sem evidência de verificação.

## Estrutura alvo da Fase 0

```text
ai-service-desk/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── local-ai-smoke.yml
├── src/
│   └── ai_service_desk/
│       └── __init__.py
├── tests/
│   └── test_package.py
├── docs/
│   ├── environment/
│   │   └── local-demo.md
│   ├── superpowers/
│   │   ├── specs/
│   │   └── plans/
│   └── roadmap.md
├── .gitignore
├── AGENTS.md
├── README.md
└── pyproject.toml
```

### Responsabilidades

`src/ai_service_desk/` é o pacote Python oficial do produto. Na Fase 0 deve conter apenas o mínimo necessário para provar instalação e importação.

`tests/` começa com testes estruturais simples. Não deve simular lógica de negócio inexistente.

`docs/environment/local-demo.md` registra o ambiente real de homologação do Dell, incluindo Windows, Python, Ollama, modelos e runner self-hosted.

`docs/superpowers/specs/` contém especificações aprovadas. `docs/superpowers/plans/` conterá planos de implementação criados após aprovação das respectivas especificações.

`docs/roadmap.md` descreve a sequência macro do produto e não funciona como backlog detalhado.

`README.md` deve ser curto e operacional. `AGENTS.md` deve ser curto e normativo.

## Itens que não entram na Fase 0

Não criar nesta fase:

- lógica do motor atual;
- corpus TI real;
- API web;
- banco de dados;
- frontend ou diretório `web/`;
- Docker ou infraestrutura de deploy;
- `.env.example` sem requisito concreto;
- dependências de LLM, embeddings ou retrieval no pacote Python;
- abstrações antecipadas para provedores ou integrações futuras.

Esses elementos serão introduzidos somente quando uma fase específica exigir.

## Fluxo de desenvolvimento

A linha de trabalho padrão será:

```text
main
↓
branch curta por fase ou tarefa
↓
desenvolvimento
↓
pytest + ruff local
↓
pull request
↓
CI hospedado
↓
revisão
↓
merge em main
```

O primeiro workflow criado diretamente em `main` foi uma exceção necessária para inicializar e validar o repositório vazio. As mudanças seguintes devem respeitar branch e pull request.

## CI determinístico

O workflow `ci.yml` deve rodar automaticamente em pull requests e executar somente validações determinísticas.

Fluxo esperado:

```text
Python 3.14
pip install -e .[dev]
ruff check .
ruff format --check .
pytest
```

A função desse workflow é verificar instalação, estilo, lint e testes sem depender do notebook Dell, Ollama, modelos locais ou serviços externos.

## Homologação local com Ollama

O workflow existente `local-ai-smoke.yml` permanece separado do CI determinístico e deve ser disparado manualmente por `workflow_dispatch`.

Runner esperado:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

O ambiente atualmente validado é:

```text
Windows 11 Pro
Python 3.14.7
Ollama 0.33.3
qwen3.5:4b
qwen3-embedding:0.6b
Ollama API: http://localhost:11434
Runner: ai-service-desk-dell
Runner mode: interativo via run.cmd
Runner service: Stopped + Disabled
```

O runner interativo deve executar na sessão `juparana-pgm\pedro.borges`, pois é nela que Python e Ollama estão disponíveis.

O comando operacional é:

```powershell
cd C:\actions-runner
.\run.cmd
```

O serviço Windows do runner permanece desabilitado durante desenvolvimento e demonstração. Não faz parte desta fase reparar a relação de confiança do domínio ou criar uma conta de serviço corporativa.

O workflow local deve falhar de forma explícita quando Python, Ollama ou algum modelo obrigatório não estiver disponível. Não deve existir fallback silencioso.

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. Ele não é uma dependência conceitual permanente da arquitetura futura do produto web.

## Regra para GitHub Actions remoto

Quando uma validação depender do runner self-hosted ou de CI remoto:

1. disparar ou identificar a execução;
2. informar o que precisa concluir;
3. parar;
4. o operador acompanha a execução no GitHub e retorna com status ou log.

Não realizar polling repetitivo de GitHub Actions.

## Dados e segredos

### Permitido

- corpus real preparado para o produto, a partir da Fase 1;
- fixtures pequenas e sanitizadas para testes;
- arquivos de configuração sem credenciais.

### Fora do Git por padrão

- exports brutos do TiFlux;
- embeddings gerados;
- caches;
- logs;
- relatórios temporários;
- artefatos derivados que possam ser reproduzidos.

### Proibido

- senhas;
- tokens;
- cookies de sessão;
- chaves de API;
- credenciais;
- arquivos `.env` com valores reais;
- qualquer segredo encontrado acidentalmente em exports ou dados preparados.

Antes de versionar o corpus preparado na Fase 1, deve existir um gate específico para confirmar formato, tamanho, colunas necessárias e ausência de credenciais acidentais.

## `.gitignore`

A fundação deve ignorar pelo menos:

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
.env
.env.*
dist/
build/
*.egg-info/
```

Diretórios de artefatos adicionais serão incluídos quando passarem a existir.

## Documentação e governança

### `README.md`

Deve explicar de forma curta:

- objetivo do projeto;
- preparação do Python 3.14;
- criação de `.venv`;
- instalação com `pip install -e .[dev]`;
- execução de `pytest` e `ruff`;
- localização de specs, planos e documentação de ambiente;
- como encontrar as instruções da homologação local.

### `AGENTS.md`

Deve conter regras normativas, incluindo:

- trabalhar em branch curta e integrar por pull request;
- usar TDD para comportamento de produto;
- executar `pytest` e `ruff` antes de concluir uma mudança;
- nunca versionar segredos;
- respeitar a política de dados;
- manter exports brutos fora do Git;
- manter arquitetura detalhada fora de `AGENTS.md`;
- não fazer polling de GitHub Actions;
- não afirmar sucesso sem verificação recente.

### Roadmap macro

O arquivo `docs/roadmap.md` deve registrar a direção atual:

```text
Fase 0  Fundação do repositório
Fase 1  Motor atual reproduzível
Fase 2  Retrieval no corpus TI real
Fase 3  Avaliação e calibração
Fase 4  FAQ e base de conhecimento
Fase 5  Triagem conversacional
Fase 6  Playbooks
Fase 7  Policy engine
Fase 8  Execução controlada
Fase 9  Integrações de sistemas
Fase 10 Escalonamento e roteamento
Fase 11 Aprendizado e prevenção
Fase 12 Interface web e demonstração final
```

As fases futuras representam direção, não especificações congeladas. Cada fase deve receber sua própria especificação e critérios de saída quando chegar o momento de implementá-la.

## Critérios de conclusão da Fase 0

A Fase 0 só pode ser considerada concluída quando houver evidência de que:

- a estrutura do repositório corresponde ao desenho aprovado;
- Python 3.14 está declarado como requisito;
- o pacote pode ser instalado em modo editável;
- `import ai_service_desk` funciona no ambiente instalado;
- `pytest` está configurado e passa;
- `ruff check .` passa;
- `ruff format --check .` passa;
- o CI hospedado executa automaticamente em pull request;
- o smoke test local permanece separado e manual;
- a documentação do Dell e Ollama está registrada;
- a política de dados e segredos está registrada;
- `AGENTS.md` contém as regras operacionais aprovadas;
- o roadmap macro está registrado;
- nenhuma lógica do motor foi migrada antecipadamente;
- nenhuma dependência de IA foi adicionada ao pacote Python;
- a mudança é revisada por pull request antes de entrar em `main`.

O fluxo mínimo reproduzível esperado é:

```text
clone do repositório
↓
Python 3.14
↓
criação de .venv
↓
pip install -e .[dev]
↓
ruff check .
↓
ruff format --check .
↓
pytest
↓
import ai_service_desk
↓
PR validado pelo CI hospedado
```

A homologação local é uma evidência separada e deve continuar comprovando o caminho GitHub Actions, runner Windows, Python local, Ollama e os dois modelos obrigatórios.

## Regra para as fases seguintes

Cada fase futura deve possuir critérios mensuráveis de saída antes de começar a implementação. O projeto não avança para a fase seguinte apenas porque a anterior parece funcional. A transição exige evidência compatível com os critérios definidos na respectiva especificação.
