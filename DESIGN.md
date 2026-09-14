# Sistema visual do Jup Resolve

Direção de frontend atualizada em 14/09/2026 a partir do ZIP `jup-ui-central-suporte.zip` e do briefing explícito do usuário. Substitui a direção visual anterior da Fase 14.

## Linguagem compartilhada

Inter, servida localmente com licença OFL, verde estrutural `#45813c`, verde profundo `#173e25`, amarelo de acento `#eeb41e`, canvas `#f6f8f5` e superfícies brancas. Tokens em `web/src/tokens.css`; componentes e layouts em `web/src/styles.css`. As camadas antigas `premium.css` e `showcase-desktop.css` foram removidas.

Navbar de 80 px com Soluções e Falar com o Jup, sidebar contextual de 232 px somente na conversa e na operação, controles compactos, raios de 8 a 22 px e transições de 150–180 ms. Desktop prioritário em 1440, 1600 e 1920 px. Sem refinamento mobile nesta missão; navegação e conteúdo continuam acessíveis em larguras menores.

## Superfícies

- Central editorial sem sidebar, hero central, busca destacada, pills e quatro categorias expansíveis. Por orientação explícita posterior do usuário, a composição contém 17 títulos do ZIP; 16 são exemplos não interativos. Somente o tutorial CDM `KB-SYN-FAQ-CDM-REQUEST-001`, disponível no backend, possui link funcional.
- Artigo com breadcrumb, conteúdo aprovado literal, endereço oficial e continuidade com o Jup.
- Chat com sidebar Nova conversa / Acompanhar chamado / Artigos de ajuda; boas-vindas centralizadas dentro da conversa, com avatar original ampliado e sem hero permanente; conversa à esquerda e coluna de artigos relacionados e apoio à direita. Mensagens alinhadas por autor, horário de apresentação e composer compacto mantêm o comportamento já validado.
- Operação com fila, detalhe, policy, routing, contexto e timeline reais; encaminhamentos de suporte mostram o resumo armazenado no backend.
- Solicitações do usuário com status e detalhe expansível.

## Interação e autoridade

O menu de usuários lista identidades retornadas pelo provider; as rotas mantêm o mapeamento demo existente. O backend valida cada chamada. Novo chat reinicia somente contexto conversacional da identidade, preservando solicitações e encaminhamentos.

No primeiro envio, as boas-vindas saem em 280 ms e cedem lugar à mensagem e ao processamento. Os demais envios mantêm a entrada já estabelecida. A resposta bem-sucedida respeita um mínimo visual de 2,4 segundos contado desde o envio; backend lento não recebe atraso adicional. O indicador mostra “Pensando...” e “Buscando contexto”, com CDM ou 365 quando mencionado nas mensagens. O rótulo é contextual de apresentação, sem descrever raciocínio ou etapas internas do backend. Erros aparecem sem espera artificial. Redução de movimento desativa as animações.

`REQUEST_CREATED` mantém estado `success`; handoffs de suporte usam `escalation`; `warning` usa o emote sem rosto. Dados e links são escapados; somente destinos oficiais explicitamente permitidos são clicáveis. A CSP permanece restrita à própria origem.


## Correção editorial da Central e do artigo CDM

Central e artigo pertencem ao modo de leitura: página branca, navbar em neutral-100, conteúdo organizado por largura de leitura, espaços e divisórias. Não há superfície própria ou card externo na Central, no diretório ou no artigo. CTAs finais integram o fluxo da página. A callout de segurança conserva sua função semântica com linha lateral discreta. A representação da scrollbar é oculta somente nas páginas públicas de ajuda; rolagem nativa permanece habilitada e a conversa conserva sua scrollbar.

O welcome usa uma única transição de entrada na página vazia, inclusive ao retornar de Soluções e após Nova conversa. A largura do bloco é reservada. O corpo do avatar no welcome acomoda-se uma vez; piscadas e emotes continuam animados, enquanto a camada invisível fica pausada. Mensagens progressivas e contratos não mudam.

Ajuste final autorizado: o CTA da FAQ fica fixo no rodapé da viewport, com espaço inferior reservado no documento. Títulos de categorias exibem texto, contagem e chevron, sem ícones decorativos. O CTA do artigo continua no fluxo normal.
