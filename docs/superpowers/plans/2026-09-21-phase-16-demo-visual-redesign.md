# Redesign visual da demo — Plano de implementação

> **Para agentes:** executar neste checkout com `superpowers:executing-plans`, em TDD, preservando o commit único solicitado pelo usuário.

**Objetivo:** unificar chat, Central, artigo, solicitações e caixas técnicas do Jup Resolve na linguagem visual da apresentação, sem alterar contratos ou decisões do backend.

**Arquitetura:** manter o frontend vanilla e seus renderizadores puros. Centralizar identidade em tokens, assets locais e componentes compartilhados; usar GSAP/Flip somente nas transições estruturais e CSS nos estados locais. A camada de aplicação continua consumindo os endpoints existentes e passa a apresentar Técnico Geral por `/api/operations/handoffs`.

**Stack:** HTML, CSS, JavaScript ESM, Node test runner, GSAP + Flip locais, Boxicons local, Montserrat variável local, Magistral Bold WOFF2 fornecida.

**Spec:** `docs/design.md` e briefing aprovado desta rodada.

## Restrições globais

- Base lógica: `afe24d74a0ec0a49bc58814c4699a67c9f492abd`, branch `phase-16-demo-readiness`.
- Nenhuma alteração em `src/ai_service_desk/`, policy, routing, approval, grounding, CDM ou contratos backend.
- CSP same-origin, nenhum CDN e nenhum framework frontend.
- Um único commit final: `feat(web): unify demo visual system and motion`.
- Magistral apenas em display/marca; Montserrat em toda UI e leitura.
- Reduced motion preserva feedback e remove deslocamentos/staggers.

## Foco de revisão

- O composer não pode rerenderizar por tecla nem perder caret/foco.
- A resposta entra completa; nenhum texto é revelado por palavra ou caractere.
- Técnico Geral vê apenas handoffs autorizados pelo endpoint existente.
- Ordenação de filas usa `updated_at || created_at || último evento`, newest first, sem alterar dados.
- Requester não recebe metadados internos; detalhes técnicos permanecem restritos à operação.

---

### Tarefa 1: contratos de build, ícones e tipografia

**Arquivos:** `.gitignore`, `web/scripts/build.mjs`, `web/src/index.html`, `web/src/icons.mjs`, `web/src/tokens.css`, `web/tests/redesign.test.mjs`.

- [ ] Escrever testes que exijam somente as três dependências diretas e assets locais no build.
- [ ] Confirmar RED contra o build copiador atual.
- [ ] Copiar Magistral fornecida para `web/src/assets/fonts/` e vendor mínimo para `dist/vendor/`.
- [ ] Trocar o registro SVG por Boxicons Filled e carregar GSAP/Flip locais.
- [ ] Confirmar GREEN.

### Tarefa 2: identidade, roteamento e filas

**Arquivos:** `web/src/state.mjs`, `web/src/router.mjs`, `web/src/components.mjs`, `web/src/tracking.mjs`, `web/src/app.mjs`, testes correspondentes.

- [ ] Escrever testes para e-mail normalizado, Técnico Geral visível/roteado e ordenação newest first.
- [ ] Confirmar RED.
- [ ] Implementar `corporateEmailFromName`, rota `/demo/operacao/general`, inbox de handoffs e ordenação puramente apresentacional.
- [ ] Confirmar GREEN e regressão do fluxo de identidades.

### Tarefa 3: chat conversation-first e motion honesto

**Arquivos:** `web/src/components.mjs`, `web/src/presentation.mjs`, `web/src/app.mjs`, `web/src/ui-polish.mjs`, CSS e testes.

- [ ] Escrever testes para ausência do rail permanente/reveal progressivo, contador real e source card único.
- [ ] Confirmar RED.
- [ ] Implementar welcome→conversation por Flip, timer DOM-local, status→resposta por timeline e source cards progressivos.
- [ ] Confirmar GREEN, caret estável e reduced motion.

### Tarefa 4: superfícies editoriais e operacionais

**Arquivos:** `web/src/solutions.mjs`, `web/src/knowledge_content.mjs`, `web/src/tracking.mjs`, `web/src/styles.css`, `web/src/desktop-responsive.css`, `docs/design.md`, testes.

- [ ] Escrever/ajustar testes apenas para os novos contratos estruturais.
- [ ] Confirmar RED.
- [ ] Aplicar a gramática compartilhada à Central, artigo, solicitações, CDM, M365 e Geral.
- [ ] Confirmar GREEN em conteúdo longo, vazio e detalhes recolhidos.

### Tarefa 5: QA visual, detector e entrega

**Arquivos:** todas as mudanças da rodada.

- [ ] Rodar `npm test`, `npm run lint`, `npm run build` e `git diff --check`.
- [ ] Subir a aplicação real e inspecionar as superfícies/estados nas larguras 1152, 1440, 1600 e 1920, incluindo teclado e reduced motion.
- [ ] Rodar o detector Impeccable uma única vez, corrigir achados materiais em lote e confirmar visualmente uma vez.
- [ ] Executar revisão final independente, revisar o diff, confirmar ausência de CDN e de `node_modules` versionado.
- [ ] Criar o único commit, fazer push normal para `phase-16-demo-readiness` e registrar SHA/status finais.
