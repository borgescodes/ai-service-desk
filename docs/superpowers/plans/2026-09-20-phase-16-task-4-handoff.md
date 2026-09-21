# Phase 16 — Task 4: caminho demonstrável Microsoft 365

## Status

PASS. Execução inline com **GPT-5.6 Terra / Medium**, sem subagents e sem escalada.

## Entrega

- `KB-SYN-M365-PASSWORD-001` continua sendo a única fonte do procedimento aprovado. O título do artigo passou a ser **Redefinir sua senha do Microsoft 365**, sem alterar o conteúdo operacional.
- A resposta M365 entrega o artigo interno aprovado e a URL Microsoft autorizada; o grounding protege procedimento, URL e referência à Central.
- A Central exibe o artigo M365 em **Impressão, Office e aplicativos**, priorizando-o entre os itens featured sem tornar os artigos cenográficos funcionais.
- O renderer foi generalizado por `knowledge_id` aprovado para os dois artigos funcionais (CDM e M365), com um único layout e sem procedimento duplicado no frontend.
- O resultado positivo permanece resolvido e sem handoff. O negativo reutiliza o handoff M365 existente, com `TECH-M365`, procedimento entregue e resultado relatado no contexto técnico.

## Grounding

O writer não pode introduzir notificação, retorno futuro, contato, status ou procedimento. Uma tentativa de acrescentar “técnico foi notificado” e “você receberá retorno” recai no fallback factual protegido. O contrato CDM da Task 3 foi mantido.

## Validações

- Testes focados cobrem artigo M365 no retorno, URL oficial, prioridade do artigo na Central, navegação, renderer, conteúdo protegido, positivo/negativo e handoff.
- Frontend: testes, lint e build executados.
- Visual local: artigo aparece na categoria correta, abre o detalhe, identifica a página oficial Microsoft, mantém o layout e oferece continuidade com o Jup.
- Ollama real com `qwen3.5:4b` e `qwen3-embedding:0.6b`: cenário positivo e negativo aprovados, **2 passed em 147,06 s**. O registro local permanece ignorado em `reports/task4-ollama-real.*`.
- Suíte Python completa: **1348 passed, 31 skipped**, em 190,87 s. Ruff, diff check, testes, lint e build frontend aprovados.

## Limitações

Não foram implementados `/solicitacoes`, retenção de chat na troca de persona, triagem geral, novos artigos, API produtiva CDM ou polish visual global.

## Próxima task

Task 5: **GPT-5.6 Terra / Medium**. Escalar para Sol / Medium somente se o estado de solicitações exigir mudança compartilhada não trivial.
