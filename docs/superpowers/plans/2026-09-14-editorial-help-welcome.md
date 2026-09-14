# Correção editorial e ciclo do welcome

Base: `9569bf5dce0d2cc5e66b9bd67b0313b54f2fca84`. Trabalho inline na branch autorizada `codex/jup-frontend-redesign`. Não fazer commit ou push antes da homologação explícita do usuário.

## Referências e limite

Briefing do usuário é autoridade visual. A referência SAP fornece somente os princípios de navbar contrastante, página branca e FAQ organizada por linhas. Impeccable e https://interfaces.rauno.me/ orientam refinamento, estabilidade geométrica e pausa das animações invisíveis. Não há cópia de marca, mudança de knowledge ou redesign das superfícies operacionais.

## Causas observadas antes de editar

`welcomePresented` era um marcador de sessão: permanecia verdadeiro ao sair do chat vazio e voltar. Nova conversa o reinicializava, por isso os dois caminhos produziam apresentações diferentes. A regressão substitui o marcador por um ciclo de visibilidade do welcome. Reentrada vazia e reset autorizado executam a mesma apresentação; histórico não entra nesse ciclo.

No avatar, amostras reais mostraram `jup-breathe` ainda executando no corpo após o typewriter: deslocamento de até 1,5 px e rotação de 1°. O bloco de largura variável também mudou o alinhamento em aproximadamente 0,016 px quando a frase terminou. A correção reserva a largura do welcome, remove o scale do crossfade e substitui somente o balanço do corpo idle no welcome por acomodação finita. Piscadas, listening e demais estados são mantidos; camadas invisíveis pausam suas animações.

## Apresentação editorial

CSS remove superfícies, bordas externas e arredondamento do diretório, Central e artigo. Usa tokens existentes, divisórias, leitura limitada a 70ch e nota de segurança com linha lateral. Breadcrumb, símbolo CDM, answer, listas, URL oficial e contexto from do CTA permanecem preservados. Scrollbar visual oculta nas páginas públicas de ajuda, mantendo wheel e teclado; chat não recebe essa regra.

## Validação e homologação

Regressões Node cobrem navegação vazia, rerender, Nova conversa e histórico ativo. QA em Edge real cobre FAQ/artigo em 1366×768, 1440×900, 1600×900 e 1920×1080, com wheel/teclado, categorias independentes e comparação das posições da navbar entre FAQ e artigo. Dez amostras após o typewriter verificam posição invariável da stack e transform identidade no corpo do avatar idle.

Capturas e roteiros em `artifacts/redesign/editorial-*`, fora do Git. Ao apresentar os checks e capturas, parar para homologação; não publicar esta rodada automaticamente. A aplicação mantém o comportamento preexistente de reload, sem adicionar persistência de conversas.
