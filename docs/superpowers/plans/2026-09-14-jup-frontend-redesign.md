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

## Correção de aderência visual

O usuário revisou os screenshots e pediu maior fidelidade estrutural. A correção recupera a FAQ sem sidebar, navbar com dois destinos, pills e categorias com os títulos ilustrativos do ZIP, deixando apenas CDM interativo. O chat recupera a coluna lateral direita e a organização contextual; envio, timing, estados do avatar e contratos permanecem preservados. Comparação lado a lado em `artifacts/redesign/comparison.html` e capturas correspondentes, fora do Git.


## Entrada da conversa e processamento

Sem mensagens, o chat apresenta o avatar original ampliado e textos de boas-vindas centralizados dentro da conversa, mantendo o composer disponível. O primeiro envio oculta o bloco em 280 ms, seguido pela entrada da mensagem e do processamento. Não existe hero permanente nem mensagem sintética de saudação. Nova conversa restaura esse estado e preserva solicitações existentes.

“Pensando...” acompanha uma linha contextual CDM, 365 ou neutra, derivada das menções na conversa; não representa raciocínio interno ou telemetria do backend. Redução de movimento dispensa transições. FAQ, coluna de apoio, handoff e duração mínima de apresentação da resposta permanecem preservados.

Validação desta rodada: 94 testes Node, build e lint; QA real em 1440 px com captura do estado inicial, saída, processamento CDM/365 e reset, além da verificação de solicitações preservadas. Evidências em `artifacts/redesign/chat-*.png` e `chat-entry-qa.cjs`, fora do Git.
