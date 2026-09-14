# Reconstrução do frontend — execução

Briefing e direção visual fornecidos pelo usuário em 14/09/2026. Trabalho inline, sem subagentes, no clone principal.

## Base confirmada

- Branch inicial `main`, limpa, HEAD `a4c4dc25afd07f449036dd837dbcfa4a219806c2`.
- Fetch confirmou PR #17 aberto e Draft, HEAD `ff752e4d415ff9c0b2dce312559706194e06ada7`.
- Branch local de trabalho `codex/jup-frontend-redesign`, criada desse HEAD sem alterar os worktrees existentes.
- Python global apontava para outro checkout. Todas as verificações e o servidor desta missão usam `PYTHONPATH` definido para `src` deste clone.

## Sequência

1. Inspecionar ZIP, handoff, vídeo, rotas, provider, contratos e avatar.
2. Testar reset conversacional que preserve solicitações e handoffs.
3. Consolidar tokens, fontes locais, navbar, sidebar e componentes.
4. Reconstruir Central CDM, artigo, chat e estados de processamento.
5. Ligar personas existentes e proteger respostas assíncronas contra troca de contexto.
6. Mostrar solicitações e encaminhamentos técnicos reais.
7. Validar desktop no browser, executar regressões e smokes.
8. Publicar candidate por push normal, mantendo PR Draft e sem polling de CI.

## Extensões mínimas de contrato

- `POST /api/jup/conversation/reset`: exige solicitante, limpa contexto e incrementa geração da conversa; preserva registros de atendimento.
- `GET /api/operations/handoffs`: exige técnico e filtra pelo responsável armazenado no handoff.

Nenhuma mudança em policy, routing, integração CDM ou corpus. A FAQ conversacional permanece separada do tutorial.

## Evidências locais

Testes RED/GREEN cobrem reset, autorização, preservação de solicitações/handoffs, personas, envio, espera visual e isolamento de respostas tardias. Capturas e scripts de QA ficam em `artifacts/redesign/`, fora do Git. Os detalhes finais de verificação pertencem ao candidate e ao PR.
