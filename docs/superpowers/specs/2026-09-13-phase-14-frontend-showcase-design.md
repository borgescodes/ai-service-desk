# Fase 14 — Central de ajuda e conversa Jup

Direção aprovada pelo solicitante em 13/09/2026. Execução inline, sem agentes,
push, merge ou alteração das integrações CDM. Base: 3a7d28f734eb4dbf89ca14383ec0ce84f2518219.

## Tese visual

A ajuda acompanha a rotina da Juparanã. Busca ampla domina o primeiro viewport;
linhas editoriais substituem a distribuição uniforme em quatro colunas.
Verde institucional, branco e neutros existentes recebem linhas curvas discretas,
inspiradas no ritmo do cultivo, sem fotografias ou ícones temáticos. Fontes locais,
paleta de DESIGN.md preservada. Home em modo Read; conversa em modo Operate.
No desktop, resultados e sugestões têm pesos diferentes; no mobile, a mesma
hierarquia flui em uma coluna. O gesto característico é selecionar um tópico
e ver a lista responder, com contexto de busca preservado.

## Reuse, create e impacto

Reutilizar API, conteúdo literal, renderizador seguro, ES modules, seis estados
do Jup e shell PNG. Criar fonte FAQ-only, quatro categorias na projeção,
cenários sem knowledge_id e controlador de scroll. Refazer home e conversation
container. Não alterar classification, policy, identidade, retrieval, playbooks,
fake CDM nem integração real. Atualizar somente contratos públicos aditivos.

## Arquitetura de conteúdo

write_demo_faq_knowledge grava artigos SYNTHETIC_DEMO / APPROVED com revisão,
data e versão explícitas, usando exclusivamente campos do schema existente.
DemoFaqCatalog recebe a fonte adicional. build_knowledge_index continua recebendo
somente write_demo_knowledge; os dois IDs operacionais permanecem inalterados.
Tutorial CDM: KB-SYN-FAQ-CDM-REQUEST-001. Não substitui KB-SYN-CDM-ACCESS-001.
Referência funcional somente leitura: juparana-dev/cdmjuparana,
SHA 3b5a1c76a50d44857263538864332adc4acb0cf8, formulário, painel, functions e guia
de autenticação. Copy segue o fluxo desejado aprovado, sem seleção de papel.

Tags faq-acessos-rotinas, faq-erros-sistemas, faq-impressao-office-aplicativos
e faq-rede-internet definem os quatro grupos. Fallback para artigos históricos
usa problema/intent e sistema, exclusivamente no catálogo. category_key é público.
Busca aceita category, desconhecida retorna vazio. Limites históricos preservados.
Detalhe apresenta provenance da demonstração; resumo não expõe dados de revisão.
Cenários são rascunhos editáveis, sem envio automático nem orientação oficial.

## URLs seguras

APPROVED_PROCEDURE_URLS associa IDs exatos a URLs constantes do backend.
CDM somente no tutorial novo; M365 mantém a URL homologada. Texto nunca é
auto-linkificado. Frontend aceita apenas essas URLs exatas projetadas; CDM exige
o ID do tutorial. Nenhuma query altera identidade, autorização ou estado.

## Modelo de conversa

Cada resposta contém avatar de 44px (38px mobile), autor discreto, texto flat e
blocos estruturados associados àquela resposta. Usuário à direita com superfície
contida. Boas-vindas é mensagem contextual, sem hero/avatar separado.
Thinking é mensagem temporária com avatar e três pontos. Falhas são mensagens
com warning sem rosto. Sucesso transita para idle; handoff conserva seu emote.
Idle/listening/thinking têm loops sutis; reduced motion mantém estados legíveis.
Scroll interno registra proximidade ao fim antes de atualizar mensagens, conserva
a posição de quem está lendo acima e oferece botão para retornar ao fim.
Composer no rodapé, textarea, Enter/Shift+Enter, foco e loading explícitos.

## Riscos e critérios de aceitação

- Fonte FAQ-only não pode participar do índice conversacional, inclusive após reset.
- Query e filtro se combinam; respostas atrasadas não sobrescrevem navegação.
- Rascunho não envia, não contém identidade e sobrevive à renderização.
- Atualização de mensagens não sequestra scroll/foco; composer não cobre conteúdo.
- Todos os testes históricos preservados; novos testes demonstram RED/GREEN.
- Gates Python, frontend, static serving, smokes e diff check passam.
- QA real: 1600, 1280, 768 e 390; home, filtros, vazio, artigo e conversa,
  thinking, M365, CDM, handoff/erro, teclado e reduced motion.
- Revisão inline; screenshots e limitações registrados. Sem alegar aprovação
  visual de estados que não tenham sido efetivamente inspecionados.
