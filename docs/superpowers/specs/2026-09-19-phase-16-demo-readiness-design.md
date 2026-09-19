# Phase 16 - Demo Readiness

## Status

Design aprovado para planejamento.

Esta fase prepara o Jup Resolve para a demonstração da competição. O objetivo não é transformar o protótipo em um Service Desk completo, e sim provar, com poucos cenários de alta qualidade, que a arquitetura e a experiência propostas são viáveis.

A arquitetura consolidada permanece:

> LLM entende e conversa. Backend decide e executa.

## Objetivo da demonstração

A demo deve provar que o Jup consegue:

1. compreender quem é o usuário autenticado;
2. usar identidade e contexto confiáveis sem pedir novamente dados já disponíveis;
3. conversar naturalmente;
4. consultar conhecimento aprovado;
5. executar triagem limitada e útil;
6. criar e acompanhar solicitações;
7. detectar divergências entre perfil e pedido;
8. encaminhar contexto suficiente para um técnico;
9. preservar continuidade entre as superfícies da demonstração;
10. apresentar uma experiência visual coerente com a apresentação do Jup Resolve.

## Limites da fase

Não é objetivo desta fase:

- cobrir todas as áreas de TI;
- criar uma base de conhecimento completa;
- substituir um Service Desk corporativo;
- criar autenticação corporativa real;
- otimizar profundamente a latência do modelo;
- integrar obrigatoriamente com a API produtiva do CDM;
- exibir chain-of-thought ou detalhes internos ao solicitante.

## Princípios

### 1. Identidade é contexto confiável

A UI de demonstração deve permitir configurar uma identidade sintética com:

- nome;
- e-mail corporativo;
- cargo;
- área de atuação.

Exemplo:

- Nome: Ana da Silva
- E-mail: ana.silva@juparana.com.br
- Cargo: Analista UBS
- Área: UBS

A identidade configurada representa o usuário autenticado que, em produção, seria entregue pelo sistema hospedeiro.

O usuário não pode mudar nome, cargo, e-mail ou área confiáveis apenas dizendo isso ao Jup na conversa.

### 2. A área da identidade pode ser qualquer valor

A UI não fica limitada a Revenda, UBS e Fazenda.

Exemplos válidos:

- Revenda
- UBS
- Fazenda
- Financeiro
- Logística
- Controladoria
- qualquer outro texto válido de área

A área da identidade e os escopos suportados pelo CDM são conceitos independentes.

### 3. Escopos do CDM são um catálogo separado

No contrato conhecido atualmente, os business_scopes do CDM são:

- revenda;
- ubs;
- fazenda.

A arquitetura deve tratar esses valores como catálogo do CDM, não como enumeração global da identidade do usuário.

O desenho deve permitir que, futuramente, o adapter/API informe novos escopos sem exigir condicionais espalhadas pelo sistema.

Exemplo futuro:

- revenda;
- ubs;
- fazenda;
- financeiro;
- logistica.

### 4. Papel CDM e área não são a mesma coisa

Uma solicitação de acesso ao CDM possui, conceitualmente:

- e-mail;
- requested_role;
- business_scopes.

No contrato real conhecido:

requested_role:
- solicitante;
- aprovador.

business_scopes:
- revenda;
- ubs;
- fazenda.

Nome, cargo e departamento pertencem ao contexto da identidade e não devem ser tratados como requested_role.

### 5. Resolução de escopo CDM

Quando existir correspondência inequívoca entre a área confiável da identidade e um escopo disponível no CDM, o Jup pode propor esse escopo automaticamente.

Exemplo:

Área: UBS  
Pedido: "Quero acesso ao CDM."

Resultado esperado:

- requested_role mínimo: solicitante;
- business_scope: ubs.

Quando não houver correspondência, o Jup não inventa uma associação.

Exemplo:

Área: Financeiro  
Escopos conhecidos do CDM: Revenda, UBS e Fazenda.

O Jup deve explicar naturalmente que precisa saber para qual área disponível no CDM o acesso é necessário.

### 6. Divergência entre área da identidade e escopo solicitado

Uma divergência não deve ser escondida nem automaticamente negada.

Exemplo:

Área confiável: Revenda  
Usuário: "Quero acesso ao CDM para UBS."

O Jup deve:

1. reconhecer que o pedido é para UBS;
2. reconhecer que a identidade está associada a Revenda;
3. explicar a divergência em linguagem simples;
4. confirmar a intenção quando necessário;
5. registrar a solicitação com a divergência sinalizada para análise.

A superfície técnica deve permitir visualizar:

- solicitante;
- e-mail;
- cargo;
- área de atuação;
- escopo solicitado;
- papel solicitado;
- divergência, quando houver.

## Experiência conversacional

### Saudação contextual

Em uma nova conversa, o Jup pode usar o primeiro nome uma vez.

Exemplo:

"Olá, Pedro! Como posso ajudar?"

O nome não deve ser repetido artificialmente em todas as respostas.

### Nova conversa

O botão Nova conversa continua sendo a ação explícita para reiniciar a conversa.

Nova conversa:

- limpa histórico conversacional;
- limpa triagem em andamento;
- permite nova saudação contextual;
- não apaga solicitações já materializadas;
- não apaga encaminhamentos já materializados.

### Linguagem orientada ao usuário

A experiência do solicitante deve evitar termos como:

- backend;
- handler;
- policy engine;
- capability;
- knowledge_id;
- confidence score;
- MODEL_INFERRED;
- TRUSTED_SESSION;
- semantic classifier;
- vector index;
- fallback.

Esses conceitos continuam podendo existir internamente.

O solicitante deve receber linguagem como:

- "Encontrei uma orientação para esse caso."
- "Preciso confirmar uma informação antes de continuar."
- "Esse acesso precisa de aprovação."
- "Encaminhei seu atendimento para o suporte."
- "Não encontrei uma orientação validada para esse problema."

Detalhes técnicos relevantes podem aparecer apenas na superfície do técnico, de forma subordinada.

## Fluxo CDM

### Pergunta informativa

Exemplo:

"Como consigo acesso ao CDM?"

O Jup deve:

1. reconhecer a intenção informativa;
2. apresentar o artigo aprovado;
3. explicar de forma curta;
4. oferecer continuidade natural.

Exemplo:

"Se quiser, posso registrar a solicitação para você."

### Pedido de execução

Exemplo:

"Pode solicitar para mim."

O Jup reutiliza identidade e contexto já consolidados.

Ele não deve pedir novamente nome ou e-mail quando esses dados já existem na sessão.

### Contrato real como referência

A simulação deve permanecer conceitualmente compatível com o contrato real conhecido do CDM.

A integração produtiva não faz parte do gate prioritário desta fase.

## Microsoft 365

O fluxo de senha Microsoft 365 deve possuir caminho demonstrável completo.

### Orientação

O Jup deve:

1. reconhecer problema de acesso/senha;
2. consultar conhecimento aprovado;
3. apresentar a orientação;
4. disponibilizar artigo interno da Central de Suporte;
5. manter referência oficial autorizada quando aplicável.

### Resultado positivo

Exemplo:

"Deu certo, consegui entrar."

Resultado:

- atendimento resolvido;
- resposta natural;
- nenhum encaminhamento desnecessário.

### Resultado negativo

Exemplo:

"Não deu certo, continua dizendo que a senha está errada."

Resultado:

- encaminhamento para suporte Microsoft 365;
- resumo da tentativa realizada;
- contexto suficiente para o técnico;
- nenhuma promessa inventada de prazo ou contato.

## Central de Suporte

A Central permanece propositalmente cenografada.

Não é necessário tornar todos os artigos funcionais.

Nesta fase devem existir pelo menos dois artigos realmente funcionais:

1. Como solicitar acesso ao CDM.
2. Redefinir sua senha do Microsoft 365.

Os demais podem continuar como composição visual da demo.

## Minhas solicitações

O solicitante deve conseguir consultar suas solicitações por linguagem natural e por atalho de UI.

### Linguagem natural

Exemplos:

- "Como estão minhas solicitações?"
- "Tenho alguma solicitação pendente?"
- "O que aconteceu com meu pedido do CDM?"

O backend consulta apenas solicitações pertencentes à identidade confiável da sessão.

### Slash command

Ao digitar "/" no composer, a UI deve apresentar um pequeno command menu.

Escopo mínimo funcional:

`/solicitacoes`  
Ver minhas solicitações e seus status.

Não é necessário criar uma biblioteca extensa de slash commands.

O comando não cria uma segunda regra de negócio.

Tanto a linguagem natural quanto `/solicitacoes` devem consumir a mesma capacidade autoritativa de consulta.

A resposta no chat pode resumir os pedidos e oferecer CTA para `/requests`.

## Continuidade entre solicitante e técnico

Visitar uma superfície técnica e retornar ao solicitante não deve apagar a conversa existente.

Enquanto a sessão de demonstração existir, o histórico do solicitante deve ser preservado.

Apenas Nova conversa reinicia explicitamente o contexto conversacional.

## Triagem geral de TI

Existem dois comportamentos distintos.

### Cenário cenografado

Cenário recomendado:

"Meu notebook está muito lento."

O Jup deve realizar uma ou duas perguntas úteis, por exemplo:

- a lentidão ocorre desde a inicialização ou aparece depois;
- o problema afeta todo o computador ou algum aplicativo específico.

Depois, consolida o contexto e encaminha ao Técnico Geral.

### Assunto inesperado de TI sem knowledge aprovada

Exemplo:

"Meu leitor de código de barras parou de funcionar."

Quando o assunto claramente pertence a TI, mas não existe conhecimento aprovado suficiente, o Jup não deve:

- inventar procedimento;
- responder simplesmente "não sei";
- encaminhar imediatamente sem nenhum contexto;
- realizar interrogatório indefinido.

Comportamento esperado:

1. reconhecer o problema;
2. fazer no máximo uma ou duas perguntas úteis quando faltarem dados essenciais;
3. consolidar o contexto;
4. encaminhar ao Técnico Geral.

A regra é:

> Sem conhecimento aprovado, não inventa. Faz triagem útil e encaminha.

## Fora do escopo de TI

Quando o usuário perguntar algo claramente fora do papel do Jup, a resposta deve ser natural.

Exemplos:

- receita;
- esportes;
- assuntos pessoais sem relação com TI.

A resposta deve:

- demonstrar que o assunto foi entendido;
- explicar brevemente o papel do Jup;
- redirecionar para suporte/serviços de TI;
- variar naturalmente;
- evitar linguagem de policy ou mensagens rígidas.

O Jup não deve responder o conteúdo fora de escopo como especialista naquele assunto.

## Feedback durante processamento

A inferência local pode levar aproximadamente 20 segundos.

Otimização de performance não faz parte do gate prioritário desta fase.

A UI deve oferecer feedback sutil durante a espera, substituindo uma tela praticamente estática.

Exemplos de estados de apresentação:

- "Entendendo sua solicitação..."
- "Consultando as informações necessárias..."
- "Verificando orientações sobre Microsoft 365..."
- "Verificando informações de acesso ao CDM..."
- "Preparando sua resposta..."

Esses textos:

- não representam chain-of-thought;
- não revelam arquitetura interna;
- não devem afirmar etapas técnicas falsas;
- existem como feedback de espera.

O avatar pode reutilizar seus estados visuais existentes.

Motion deve respeitar prefers-reduced-motion.

## UI e identidade visual

A aplicação deve manter sua estrutura e receber polish visual orientado pela apresentação Jup Resolve.

Direção compartilhada:

- verde estrutural #45813c;
- verde profundo #173e25;
- amarelo #eeb41e como atenção/acento;
- canvas #f6f8f5;
- superfícies brancas;
- linguagem editorial limpa;
- Inter para interface operacional;
- assinatura de marca coerente com a apresentação.

O objetivo não é redesenhar toda a aplicação.

Prioridades:

1. coerência entre apresentação e demo;
2. hierarquia;
3. legibilidade;
4. organização da tela do técnico;
5. organização de Minhas solicitações;
6. estados de processamento;
7. consistência entre chat, Central e operação.

## UI do técnico

A superfície técnica deve priorizar:

- quem solicitou;
- qual problema ou pedido;
- contexto relevante;
- cargo e área;
- escopo solicitado;
- divergências;
- resumo do Jup;
- andamento;
- ação esperada do técnico.

Detalhes internos secundários devem permanecer subordinados ou em disclosure técnico.

## UI de Minhas solicitações

A tela deve permitir compreender rapidamente:

- o que foi pedido;
- sistema;
- estado atual;
- responsável, quando aplicável;
- última atualização;
- histórico básico.

Não transformar essa tela em dashboard de métricas.

## Itens pós-demo / não bloqueantes

### API real do CDM

Após concluir o pacote prioritário, avaliar se vale demonstrar efeito real ao clicar em Aprovar na superfície do Técnico CDM.

Antes de implementar, avaliar:

- autenticação;
- secrets;
- ambiente;
- risco de criar dados reais;
- contrato atual da API;
- necessidade real para a competição.

A ausência dessa integração não reprova a Phase 16.

### Performance

A latência deve ser medida novamente apenas depois do pacote prioritário estar concluído.

Otimizar somente se houver ganho seguro e de baixo risco.

A ausência de redução significativa de latência não reprova a Phase 16.

## Critérios de aceite

A parte prioritária da Phase 16 está concluída quando for possível demonstrar em uma única execução local:

1. configurar pela UI pelo menos duas identidades sintéticas diferentes;
2. aceitar áreas arbitrárias na identidade;
3. iniciar Nova conversa e receber saudação contextual pelo primeiro nome;
4. solicitar CDM sem repetir dados já conhecidos;
5. resolver automaticamente um escopo CDM quando houver correspondência;
6. lidar corretamente com área sem correspondência conhecida;
7. detectar pedido para escopo diferente da área do usuário;
8. mostrar essa divergência ao técnico;
9. consultar artigo CDM;
10. executar fluxo Microsoft 365 positivo;
11. executar fluxo Microsoft 365 negativo;
12. abrir artigo interno de redefinição de senha;
13. consultar solicitações por linguagem natural;
14. consultar solicitações por `/solicitacoes`;
15. refletir as mesmas solicitações em `/requests`;
16. visitar superfície técnica e voltar sem perder o chat;
17. usar Nova conversa para explicitamente reiniciar contexto;
18. executar o cenário cenografado de triagem geral;
19. tratar assunto inesperado de TI sem knowledge aprovada e encaminhar com contexto;
20. tratar pergunta fora de TI naturalmente;
21. apresentar feedback de processamento durante respostas lentas;
22. manter linguagem do solicitante livre de termos internos desnecessários;
23. apresentar telas de solicitante e técnico visualmente coerentes com a apresentação;
24. preservar policy, authority, grounding e segurança existentes.

## Fora do gate

Não bloqueiam conclusão:

- API produtiva do CDM;
- redução da latência do Qwen;
- cobertura completa de TI;
- dezenas de artigos reais;
- persistência de conversa entre reinícios da aplicação;
- autenticação corporativa real;
- mobile-first redesign;
- streaming de chain-of-thought;
- SSE/WebSocket apenas para simular progresso.

## Restrição final de escopo

Qualquer funcionalidade que não contribua diretamente para um critério de aceite acima deve ser tratada como fora da Phase 16, salvo aprovação explícita.
