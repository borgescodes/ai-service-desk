# AGENTS.md

## Escopo

Estas regras valem para todo o repositório AI Service Desk.

## Fluxo de trabalho

- Trabalhe em branch curta e integre mudanças por pull request.
- Não implemente uma fase futura antes de fechar os critérios de saída da fase atual.
- Use TDD para comportamento de produto: teste falhando, implementação mínima, teste passando.
- Arquivos puramente declarativos ou de configuração podem ser validados estruturalmente sem teste artificial.
- Antes de concluir uma mudança, execute `python -m pytest`, `python -m ruff check .` e `python -m ruff format --check .`.
- Não afirme sucesso ou conclusão sem evidência recente das verificações aplicáveis.

## GitHub Actions

- O CI hospedado valida mudanças determinísticas em pull requests.
- O runner Windows self-hosted é usado para homologações explícitas com Ollama.
- Não faça polling de GitHub Actions.
- Quando uma execução remota for necessária, dispare ou identifique o run, informe o que precisa concluir e pare. O operador acompanha o GitHub e retorna com status ou log.

## Dados e segredos

- Nunca versione senhas, tokens, cookies, chaves, credenciais ou arquivos `.env` com valores reais.
- Exports brutos do TiFlux ficam fora do Git.
- Dados corporativos preparados podem ser versionados quando a fase correspondente autorizar e houver verificação específica antes do commit.
- Corpus TI real não entra antes da Fase 1.
- Embeddings, caches, logs e relatórios gerados ficam fora do Git por padrão.

## Documentação

- Documentação explicativa deve ser escrita em português.
- Código, módulos, arquivos técnicos, testes e identificadores devem usar nomes em inglês.
- Mantenha este arquivo curto e normativo.
- Arquitetura detalhada pertence a `docs/superpowers/specs/`.
- Planos de implementação pertencem a `docs/superpowers/plans/`.
- Ambiente de homologação pertence a `docs/environment/`.
