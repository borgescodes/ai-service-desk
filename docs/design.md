# Sistema visual do Jup Resolve

Direção de frontend atualizada em 21/09/2026 a partir da apresentação institucional fornecida e do briefing da Fase 16. A apresentação é a autoridade visual; os screenshots da aplicação anterior servem somente como evidência dos problemas substituídos.

## Fundamentos

O produto usa Magistral Bold somente em display e momentos de marca, com Montserrat Variable em navegação, controles, dados e leitura. Ambas são servidas pela própria aplicação. A paleta estrutural parte do verde profundo `#173e25`, verde principal `#45813c`, amarelo de acento `#eeb41e`, canvas `#f6f8f5`, branco e neutros derivados de verde e cinza. Tokens vivem em `web/src/tokens.css`; não há dependência de CDN.

Raios usuais ficam entre 10 e 14 px. Pills pertencem a status e controles compactos. Superfícies usam hairlines e espaço em branco; sombras são reservadas ao composer, popover e elevação real. A interface evita card dentro de card, fundos amarelos dominantes, gradientes, glassmorphism e ornamentação gratuita.

Boxicons Filled é a família de ícones da interface. O build copia somente CSS e fonte necessários de Boxicons, Montserrat Variable e os runtimes locais de GSAP e Flip para `dist/vendor`.

## Shell e superfícies

Todas as páginas usam a mesma navbar de 76 px, fundo, logo, tipografia e estados de interação. Central de Suporte, Jup e Minhas solicitações permanecem destinos globais; a operação usa a mesma estrutura com navegação contextual. O seletor “Trocar usuário” contém Requester, Técnico CDM, Técnico Microsoft 365 e Técnico Geral, além de “Novo usuário”. O e-mail do novo requester é derivado de primeiro e último nome, normalizado e exibido como preview somente leitura.

- A Central de Suporte tem hierarquia editorial, título Magistral, busca protagonista, categorias expansíveis e linhas de artigos enriquecidas. Não há grade de cards nem CTA fixo cobrindo o conteúdo.
- O artigo mantém literalmente o conhecimento aprovado. Procedimentos numerados viram uma sequência visual, com medida de leitura de 68–70 caracteres, ação oficial, callout de segurança e continuidade com o Jup.
- O chat é conversation-first: leitura central de até 850 px, poucas molduras, mensagens distintas sem bubbles grandes, composer flutuante estável e Jup reconhecível. Artigos aparecem como source strips compactas somente quando o backend devolve referência `APPROVED`; resumos de solicitações usam linhas editoriais com hairlines, sem reutilizar cards operacionais.
- Minhas solicitações usa uma lista editorial de largura ampla, com status, atualização e responsável comparáveis de relance, e detalhe integrado abaixo. As caixas técnicas mantêm master-detail para triagem, mas a fila é uma lista de trabalho densa de aproximadamente 72 px por item. Em ambos os casos, os itens mais recentes ficam no topo por `updated_at`, `created_at` ou último evento.
- Técnico Geral usa exclusivamente os handoffs já autorizados por `/api/operations/handoffs`. Contexto do usuário, resumo do Jup, conversa e metadados técnicos são separados; tokens internos ficam em “Detalhes técnicos”.

## Motion e continuidade

A animação explica mudança de estado. No primeiro envio, GSAP Flip preserva a continuidade do avatar entre o welcome e a conversa em 460 ms. O welcome de uma conversa realmente vazia revela deliberadamente suas duas linhas uma única vez. Quando uma nova resposta completa chega do backend, a camada de apresentação divide apenas seus nós de texto em pequenos grupos e os revela progressivamente, preservando a estrutura HTML, links, listas e a resposta autoritativa. A duração varia de 700 ms a no máximo 3 s; histórico e `prefers-reduced-motion` aparecem completos imediatamente. Elementos complementares entram depois do texto. Isso não representa streaming nem chamadas de rede. O contador “Pensando · Ns” usa tempo real desde o envio e atualiza somente o nó de texto, sem rerender do chat.

Popover de persona, seleção e entrada de filas usam motion apenas quando a mudança estrutural exige continuidade; hover, foco, active e disabled ficam em CSS. A preferência `prefers-reduced-motion` elimina movimento espacial, staggers e animações repetidas, preservando conteúdo, estado, foco e feedback.

## Autoridade e segurança

A UI apresenta estado; o backend decide policy, routing, approval, execution, grounding e identidade. O requester nunca recebe dados internos como policy, confidence, capability ou origem da identidade. Na operação, esses valores ficam restritos ao disclosure técnico quando necessários. Conteúdo e links são escapados; somente destinos oficiais explicitamente permitidos são clicáveis. A CSP permanece same-origin.
