# Scroll da FAQ e apresentação progressiva do Jup

Base: `606f2cd269ec99bf63a458d9287f302fa14d0192`. Trabalho inline no clone principal, em `codex/jup-frontend-redesign`, autorizado pelo usuário. Publicação por push normal para o PR Draft #17.

## Diagnóstico e correção

A FAQ limitava a altura de body, main e diretório à viewport e movia a rolagem para um container interno. Removidas essas restrições: o card cresce com seus conteúdos e o CTA é seu irmão seguinte no DOM. Categorias independentes mantêm animação curta; auto-scroll usa window somente após abertura pelo usuário e quando o conteúdo não cabe confortavelmente.

A navbar terminava em 1425 px numa viewport de 1440 px: o root reservava 15 px com scrollbar-gutter: stable, mas seu fundo transparente deixava a área reservada visualmente distinta. O root agora pinta de branco a área de scrollbar; body pinta o canvas e ocupa ao menos a viewport. Não há largura artificial, pseudo-elemento de cobertura ou corte de overflow para esconder a borda. O gutter permanece estável entre rotas.

## Apresentação das mensagens

O renderer continua produzindo todo o HTML seguro a partir da resposta completa do backend. Apenas respostas novas do Jup recebem marcador de apresentação. A animação altera text nodes existentes, conservando elementos, atributos, links e texto final exato. Histórico, mensagens do usuário, erros e metadados de handoff não são reanimados. Cancelamento em rerender restaura imediatamente os textos completos.

A tagline usa caracteres a 28 ms após uma breve entrada. Respostas usam palavras a 30 ms, agrupadas em textos grandes para limitar a apresentação a aproximadamente 3 segundos. Thinking sai em 160 ms. Redução de movimento mostra tudo imediatamente. Não há streaming, novo estado de domínio ou mudança de contratos/allowlists.

## Evidências

115 testes Node aprovados, lint e build aprovados. QA em Edge real em 1366×768, 1440×900, 1600×900 e 1920×1080: categorias independentes, ordem inversa, fechamento intermediário, crescimento do documento, CTA externo, ausência de overflow horizontal, posições de logo/persona constantes entre quatro rotas e fundo branco do gutter.

Testes de apresentação no DOM real verificam resposta curta, múltiplos parágrafos, procedimento CDM com lista/link, identidade dos anchors e igualdade do HTML final. Fluxo real CDM e Nova conversa também verificados. Estado vazio/histórico de navegação e reduced motion permanecem funcionais. Capturas e roteiros estão em `artifacts/redesign/final-*`, fora do Git.

Limite existente: a aplicação não reidrata mensagens anteriores ao recarregar a página; abre o estado inicial. A ausência de reanimação de histórico foi verificada na navegação entre rotas, sem introduzir persistência nova nesta rodada.
