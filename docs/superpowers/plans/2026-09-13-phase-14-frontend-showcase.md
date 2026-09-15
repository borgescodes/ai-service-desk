# Fase 14 — Plano de execução inline

Execução pela skill executing-plans, sem subagents, conforme pedido explícito.

**Objetivo:** tornar a central e a conversa memoráveis sem mudar decisões do backend.
**Arquitetura:** fonte FAQ-only, projeção por tags, links explícitos, conversa contextual.
**Stack:** Python/FastAPI, vanilla ES modules, CSS e node:test.
**Spec:** ../specs/2026-09-13-phase-14-frontend-showcase-design.md

## Restrições globais

Base 3a7d28f734eb4dbf89ca14383ec0ce84f2518219; worktree phase-14-frontend-showcase.
Sem push, merge, React, novas dependências de UI ou alterações CDM/core.
Antes de Python: `$env:PYTHONPATH = (Resolve-Path .\src).Path`.
Não remover ou renomear testes históricos. Documentação em português.

## 1. FAQ e projeção

- [ ] Adicionar tests/web/test_phase14_faq.py com categorias por tags, filtro,
  combinação, vazio, APPROVED, URL exata e isolamento após reset.
  Assert principal: `set(runtime.knowledge_engine.df.knowledge_id) ==
  {"KB-SYN-CDM-ACCESS-001", "KB-SYN-M365-PASSWORD-001"}`.
- [ ] RED: `python -m pytest tests/web/test_phase14_faq.py -q`.
- [ ] Criar web/demo_faq_data.py e write_demo_faq_knowledge(path), usando
  _write_jsonl e schema existente. Acrescentar fonte apenas ao DemoFaqCatalog.
- [ ] Modificar demo_faq.py: tags, category_key, search(query, category=""),
  tabela APPROVED_PROCEDURE_URLS e provenance no detalhe.
- [ ] Encadear category em api.py e DemoRuntime.search_faq.
- [ ] GREEN: testes novos, test_demo_faq.py, test_faq_api.py e regressões runtime.

## 2. Busca, descoberta e drafts

- [ ] RED em web/tests/showcase.test.mjs e integração: quatro filtros,
  search path com categoria, vazio útil, cenários sem knowledge_id e sem POST.
- [ ] solutions.mjs mantém debounce/cancel e recebe category. Cenários usam
  /jup?draft= com texto escapado/limitado. app.mjs guarda seleção e draft;
  update de resultados preserva foco no campo e filtro.
- [ ] knowledge_content.mjs valida link CDM por ID + URL; M365 preservado.
- [ ] GREEN: `node --test web/tests/*.test.mjs`.

## 3. Conversa e motion

- [ ] RED: avatar dentro da mensagem, sem hero, thinking com dots, emotes,
  blocos anexados à resposta, draft editável, scroll próximo/distante.
- [ ] components.mjs renderiza conversation-thread com mensagens USER/JUP,
  loading e erro contextual. conversation.mjs controla scroll, botão e reduced motion.
- [ ] app.mjs conserva draft/foco/scroll, registra status/context na mensagem;
  troca success por idle após transição sem alterar dados operacionais.
- [ ] CSS substitui composição antiga e restaura loops dos assets existentes.
- [ ] GREEN: frontend completo; nenhum teste histórico alterado.

## 4. Validação e entrega

- [ ] `python -m ruff check .`; `python -m ruff format --check .`;
  `python -m pytest -q`.
- [ ] `node --test web/tests/*.test.mjs`; `node web/scripts/lint.mjs`;
  `node web/scripts/build.mjs`; static: `python -m pytest tests/web/test_api.py -q -k static`.
- [ ] Smokes CLI existentes: routing-escalation-smoke, learning-prevention-smoke,
  web-demo-smoke. Não disparar/pollar CI remoto.
- [ ] run-web-demo.cmd com PYTHONPATH; se porta ocupada, preservar processo existente
  e executar mesma CLI LOCAL_AI em porta livre, registrando a limitação.
- [ ] QA real em quatro larguras, screenshots fora do Git, estados exigidos,
  teclado/reduced motion e scroll; corrigir defeitos observados em lote.
- [ ] Detector Impeccable uma vez, revisão inline e documentação visual.
- [ ] `git diff --check`, comparação dos arquivos protegidos, diff stat/status,
  relatório com evidências. Entregar sem push e sem commit não solicitado.
