# Plano: contexto corporativo da Fase 12

Execução inline autorizada pelo usuário, sem multiagentes. Aplicar executing-plans
e TDD; a autorização já abrange design, RED, implementação e verificações.

**Objetivo:** integrar vocabulário curado sem transferir autoridade ao LLM.
**Arquitetura:** resolver F12 único injetado em três módulos neutros, com defaults
legados. Narração segura tratada separadamente.
**Tecnologias:** Python 3.14.x, Ruff 0.12.12, pytest, OllamaClient existente.
**Spec:** `docs/superpowers/specs/2026-09-10-phase-12-business-context-design.md`.

## Etapas

- [x] Sincronizar por ff-only e confirmar SHA e árvore limpa.
- [x] Escrever `tests/web/test_business_context.py` e
  `tests/engine/test_vocabulary_extension.py`: aliases/produtos, CDM conservador,
  ausência de knowledge, correção, ambiguidade e defaults legados.
  Exemplo independente: `resolver.systems('Teams no Office 365') == ('OFFICE 365',)`.
  Executar `python -m pytest tests/web/test_business_context.py
  tests/engine/test_vocabulary_extension.py -q`; registrar falhas esperadas e
  commitar RED e design.
- [x] Implementar o protocolo da spec e passagem opcional nos três módulos
  autorizados. Criar catálogo F12 e injetar em `web/demo_runtime.py`.
  Mesma instância no classificador, triagem e KnowledgeEngine. Produto vai em
  entities e contexto público; mensagem original fica intacta.
  Executar testes novos e regressões de classificação, triagem e retrieval.
- [x] Escrever RED de integração em `tests/web/test_business_context_runtime.py`
  antes de alterar a composição: Office sem clarification redundante, produto,
  correção, isolamento, prompt funcional e ausência de request inventada.
  Atualizar a expectativa obsoleta de Office preservando seu node ID.
  Completar GREEN, revisar diff e commitar implementação.
- [x] Escrever RED de alegações hostis em
  `tests/web/test_conversation_authority.py`, demonstrar a falha e commitar.
  Corrigir `web/conversation.py` por composição controlada de reconhecimento;
  manter conhecimento literal e perguntas do domínio. Executar a suíte web e
  commitar a correção separadamente.
- [x] Fixar os três blobs autorizados em `.github/workflows/phase12-web-demo.yml`.
  Verificar os demais blobs contra F11 e demonstrar que desvio nos três falha.
  Atualizar também o gate F11 e sua asserção de hashes, preservando node IDs.
- [ ] Executar full pytest, Ruff lint/format, preservação de node IDs, frontend
  lint/test/build, contrato estático, security F8–F12 e smokes F10–F12.
  Registrar versões, SHA, resultados e limites. Sem corpus bruto ou PII no diff.
- [ ] Congelar candidate, publicar na branch existente sem force push e consultar
  os cinco workflows uma única vez. Se em andamento, reportar IDs e parar.

Após cada commit, reportar SHA completo e diff. Não mergear PR, marcar Ready,
deletar branch ou alterar main. Se houver necessidade fora do escopo, parar.
