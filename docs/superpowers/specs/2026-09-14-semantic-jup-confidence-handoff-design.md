# Jup semântico, confiança explicável e handoff obrigatório

## Objetivo

Elevar a demo do Jup de um fluxo que depende demais de frases canônicas para um atendimento semanticamente robusto, preservando as invariantes já aprovadas:

- o LLM entende e conversa;
- o backend decide e executa;
- somente knowledge `APPROVED` pode orientar procedimento oficial;
- identidade é sempre fornecida pelo backend/session provider;
- nenhuma frase do usuário altera identidade confiável;
- CDM continua sendo a única integração externa automática;
- ausência de knowledge aprovada nunca autoriza o LLM a inventar procedimento;
- ausência de knowledge aprovada também não pode encerrar o atendimento sem continuidade humana.

## Problema observado na homologação

A homologação manual mostrou comportamentos que parecem de chatbot por palavras-chave:

- `deu errado` depois do procedimento Microsoft 365 não foi entendido como falha do procedimento;
- `Esqueci minha senha do office` não recuperou a mesma orientação aprovada que `esqueci a senha do microsoft 365`;
- `preciso de acesso adm no cdm` e `preciso de acesso administrativo ao cdm` foram tratados como acesso comum, gerando aprovação pendente em vez de bloqueio por policy;
- pedidos de TI sem knowledge aprovada, como lentidão do computador, terminam em abstention sem encaminhamento;
- o técnico vê uma confiança alta/baixa, mas praticamente não vê as evidências que sustentaram esse nível;
- a persona de demonstração ainda usa `Pedro Miranda`, o que deve ser substituído por uma identidade fictícia.

## Decisões aprovadas

### Persona confiável

A persona solicitante da demo passa a ser:

- Nome: `Fulano de Tal`
- Username: `fulano.tal`
- E-mail: `fulano.tal@juparana.com.br`
- Área de atuação: `Revenda - Matriz`
- Role de sessão: `REQUESTER`

Esses dados são sempre fornecidos pelo backend. Nenhum conteúdo da conversa pode substituir nome, e-mail, área ou role.

### Interpretação semântica

No modo `LOCAL_AI`, cada mensagem operacional passa por uma interpretação compacta do `qwen3.5:4b`.

O contrato deve distinguir pelo menos:

- cenário: CDM, Microsoft 365, outro TI, processo de negócio ou incerto;
- sinal conversacional: pedido de acesso, acesso privilegiado, problema de login, evidência de senha, instalação, desempenho/erro, sucesso, falha de procedimento ou desconhecido;
- indicação semântica de role privilegiado quando a linguagem natural usar variações como `adm`, `admin`, `administrador`, `administrativo`, `administradora` ou `superadmin`;
- sistema citado pelo usuário quando ele não estiver no vocabulário curado, apenas para contexto de handoff e nunca para ação automática.

O modelo não pode produzir identidade confiável, policy, aprovação, routing, request ID, estado operacional ou autorização.

A interpretação do modelo é evidência, não decisão. Antes de qualquer ação privilegiada, o backend valida texto, contexto, role e policy.

### Continuidade conversacional

O estado conversacional deve consumir os sinais semânticos retornados pelo Qwen, em vez de depender apenas de regex locais.

Exemplos obrigatórios:

- `deu errado`, `não rolou`, `continua sem entrar`, `não resolveu` após orientação Microsoft 365 devem convergir para falha de procedimento;
- `funcionou`, `agora foi`, `deu certo` devem convergir para sucesso;
- uma falha após orientação aprovada deve gerar handoff ao especialista Microsoft 365;
- o backend mantém o estado da conversa e decide se aquele sinal faz sentido naquele estágio.

### Retrieval semântico real no LOCAL_AI

No modo `LOCAL_AI`, a base de knowledge deve usar `LocalEmbedder` com `qwen3-embedding:0.6b`, já instalado no ambiente homologado.

O `DemoEmbedder` hash continua disponível para o modo determinístico e para CI reprodutível.

Consequências esperadas:

- `Office`, `Microsoft 365`, `M365` e paráfrases próximas devem recuperar a mesma orientação aprovada quando a intenção e a evidência forem compatíveis;
- o evidence gate continua obrigatório;
- nenhuma similaridade semântica pode converter knowledge `DRAFT`, `RETIRED` ou não aprovada em orientação oficial;
- o runtime não baixa modelos automaticamente;
- a inicialização LOCAL_AI deve validar `qwen3.5:4b` e `qwen3-embedding:0.6b` em localhost.

### Handoff obrigatório quando não houver knowledge aprovada

Se o Jup entender que o assunto é de TI, mas não houver knowledge `APPROVED` suficiente, o atendimento não termina em uma mensagem morta.

Regra:

1. se faltar uma informação objetiva importante, o Jup pode fazer no máximo uma pergunta curta de esclarecimento;
2. se ainda não existir orientação aprovada suficiente, o backend cria um handoff para `Técnico Geral`;
3. o Jup explica ao usuário que não possui procedimento aprovado para orientar com segurança e que encaminhou o caso;
4. nenhum procedimento técnico é inventado;
5. nenhuma ação externa é executada;
6. o handoff preserva o contexto relevante da conversa.

Exemplo:

`meu pc ta travando muito`

Resposta esperada, em conteúdo equivalente:

`Entendi que seu computador está com lentidão e travamentos. Ainda não tenho um procedimento aprovado para orientar esse caso com segurança, então encaminhei seu atendimento para o suporte técnico.`

### Técnico Geral

A identidade `tecnico-geral` deixa de ser apenas uma persona sem capacidade operacional e passa a receber handoffs internos de TI que não pertencem aos fluxos CDM ou Microsoft 365.

Isso não cria integração externa nova. O handoff é interno e não executa ação em terceiros.

A visão operacional deve permitir selecionar o Técnico Geral e visualizar seus encaminhamentos.

## Confiança explicável

### Significado da confiança

Confiança não significa autorização e não substitui policy.

Ela responde à pergunta:

`Quanto o contexto confiável conhecido sobre o solicitante é coerente com o pedido interpretado?`

A autorização continua sendo responsabilidade exclusiva da policy.

### Níveis

O contrato passa a admitir:

- `HIGH`
- `MEDIUM`
- `LOW`

A classificação deve ser explicável por reason codes estáveis e traduzidos para textos humanos na camada de apresentação.

### Evidências

A avaliação deve considerar, quando aplicável:

- identidade confirmada pelo backend;
- área de atuação confiável;
- sistema ou acesso solicitado;
- coerência entre área e sistema;
- finalidade declarada;
- perfil solicitado;
- presença ou ausência de contexto suficiente.

A confiança não deve ser um percentual inventado pelo LLM. Se houver percentual na UI, ele deve vir de um valor realmente calculado pelo backend. Caso contrário, a UI deve priorizar nível e evidências, sem número decorativo.

### CDM coerente com Revenda

Para `Fulano de Tal`, área `Revenda - Matriz`, um pedido como:

`Preciso de acesso ao CDM para solicitar materiais para revenda`

é o caso padrão de confiança alta, desde que o perfil solicitado seja não privilegiado.

Evidências esperadas:

- identidade confirmada;
- área `Revenda - Matriz`;
- sistema CDM coerente com a finalidade;
- finalidade de solicitação de materiais confirmada;
- perfil solicitado `SOLICITANTE`.

### CDM parcialmente confirmado

Um pedido genérico como:

`Preciso de acesso ao CDM`

pode ser confiança média quando a área é coerente, o sistema está claro, mas a finalidade operacional ainda não está confirmada.

Isso não impede a policy de exigir aprovação humana.

### UBS como caso padrão de confiança baixa

A demo deve reconhecer explicitamente `UBS` como acesso citado pelo usuário, mas não como integração automática nem como sistema autorizado para execução.

Para `Fulano de Tal`, área `Revenda - Matriz`, um pedido como:

`Preciso de acesso ao UBS`

é o caso padrão de confiança baixa por incompatibilidade com o contexto curado da persona.

Evidências esperadas:

- identidade confirmada;
- área confiável `Revenda - Matriz`;
- acesso solicitado `UBS`;
- ausência de coerência conhecida entre `UBS` e a área `Revenda - Matriz`;
- ausência de justificativa suficiente para elevar a confiança.

Esse pedido não é negado automaticamente apenas pela confiança. Como não existe integração automática UBS, ele deve seguir para revisão humana via Técnico Geral, com confiança `LOW` e as razões visíveis.

### Pedidos privilegiados

`adm`, `admin`, `administrador`, `administrativo`, `administradora` e `superadmin` devem convergir para intenção privilegiada controlada.

Para CDM, a policy existente continua decidindo `DENY` para roles privilegiados.

A confiança e a policy devem aparecer separadamente. É válido haver confiança alta sobre o entendimento do pedido e, ao mesmo tempo, policy `DENY`.

## Visão do técnico

A solicitação ou handoff deve mostrar primeiro fatos de negócio, não códigos internos.

### Solicitante

- nome;
- username;
- e-mail;
- área de atuação;
- origem da identidade: backend/session provider.

### Pedido

- sistema ou acesso solicitado;
- perfil solicitado, quando aplicável;
- finalidade declarada;
- escopo/área de negócio identificada, quando houver evidência suficiente;
- mensagem original relevante.

### Análise do Jup

- intenção interpretada;
- contexto/sistema;
- confiança `Alta`, `Média` ou `Baixa`;
- seção `Por que essa confiança?` com evidências positivas, faltantes e conflitantes derivadas dos reason codes do backend.

Exemplo de confiança alta:

- Usuário atua em `Revenda - Matriz`;
- pedido relacionado a solicitação de materiais;
- sistema CDM coerente com a finalidade;
- perfil solicitado `Solicitante`.

Exemplo UBS:

- Identidade confirmada pelo backend;
- área conhecida `Revenda - Matriz`;
- acesso solicitado `UBS`;
- acesso solicitado não possui coerência conhecida com a área de atuação;
- contexto insuficiente para elevar a confiança.

### Decisão do backend

Separada da análise:

- decisão de policy;
- necessidade de aprovação humana;
- routing;
- estado atual;
- informação explícita de que nenhuma execução automática ocorreu quando for o caso.

Códigos como `policy_id`, `reason_code`, capability e IDs de knowledge/playbook permanecem acessíveis em `Detalhes técnicos`, mas não devem ser a principal explicação visual.

## Nova conversa e reset

`Nova conversa` continua chamando `POST /api/jup/conversation/reset`.

Esse endpoint deve:

- limpar somente contexto conversacional, triagem e suporte da identidade atual;
- restaurar a apresentação inicial do Jup;
- preservar solicitações, aprovações, handoffs e histórico operacional já materializado.

`POST /api/demo/reset` continua sendo um reset total da demonstração e não deve ser ligado ao botão `Nova conversa`.

## Segurança

As seguintes regras são fail-closed:

- LLM nunca cria request diretamente;
- LLM nunca decide policy;
- LLM nunca aprova ou executa;
- LLM nunca altera identidade confiável;
- sistema citado fora do vocabulário curado, como UBS, pode ser preservado apenas como contexto de handoff humano;
- somente knowledge `APPROVED` pode produzir procedimento oficial;
- sem knowledge aprovada, o Jup pode esclarecer e encaminhar, mas nunca inventar instrução técnica;
- CDM permanece a única integração externa automática;
- UBS e suporte geral não executam integrações externas.

## Casos de aceitação

### Microsoft 365

Devem funcionar como equivalentes semânticos, respeitando evidence gate:

- `Esqueci minha senha do Microsoft 365`
- `Esqueci minha senha do Office`
- `Meu Office não entra` seguido de `diz que a senha está errada`

Depois da orientação:

- `deu errado`
- `não rolou`
- `não funcionou`
- `continua sem entrar`

levam a handoff para Técnico Microsoft 365.

### CDM privilegiado

Devem ser entendidos como privileged access e cair na policy de negação:

- `preciso de acesso adm no cdm`
- `preciso de acesso administrativo ao cdm`
- `preciso de acesso administrador ao cdm`
- `quero superadmin no cdm`

Nenhum deles pode criar `PENDING_APPROVAL` como `SOLICITANTE`.

### Cadastro de material

`Preciso cadastrar um material para revenda` não pode virar pedido de acesso.

Se não houver orientação aprovada para o processo, o Jup pode fazer no máximo uma pergunta curta para separar `ajuda com cadastro` de `problema de acesso`; persistindo ausência de knowledge, gera handoff humano.

### TI sem knowledge

`meu pc ta travando muito` deve resultar em uma pergunta curta somente se ela realmente reduzir ambiguidade. Sem knowledge aprovada suficiente, o caso deve ser encaminhado ao Técnico Geral.

### UBS

`Preciso de acesso ao UBS` para `Fulano de Tal / Revenda - Matriz` deve:

- preservar UBS como acesso solicitado;
- avaliar confiança `LOW`;
- explicar incompatibilidade com a área confiável;
- não executar ação externa;
- encaminhar ao Técnico Geral para revisão humana.

### Visão técnica

Na tela operacional, o técnico deve conseguir responder rapidamente:

- quem é o solicitante;
- qual é o e-mail confiável;
- qual é a área de atuação;
- o que foi solicitado;
- qual perfil foi pedido;
- por que a confiança ficou alta, média ou baixa;
- qual policy foi aplicada;
- se algo já foi executado;
- qual é o próximo passo.

## Estratégia de testes

A implementação deve ser TDD e cobrir:

- unit tests da interpretação compacta;
- unit tests da normalização de roles privilegiados;
- unit tests dos três níveis de confiança e reason codes;
- testes de integração do runtime para Microsoft 365, CDM, UBS e suporte geral;
- testes do `LOCAL_AI` opt-in com Qwen real para paráfrases naturais;
- testes de retrieval com `qwen3-embedding:0.6b` no caminho opt-in local;
- testes da API de handoff;
- testes Node da apresentação operacional e da persona;
- regressão do botão `Nova conversa` preservando requests/handoffs;
- regressão de segurança: nenhuma execução externa fora do CDM.

## Critério de conclusão

A mudança só está homologada quando:

- suítes determinísticas passam;
- Ruff passa;
- testes Node/lint/build passam;
- QA opt-in com `qwen3.5:4b` e `qwen3-embedding:0.6b` passa;
- os casos manuais acima passam no navegador;
- a visão do Técnico CDM e Técnico Geral mostra identidade, contexto, confiança explicada e decisão do backend;
- o PR permanece sem merge até autorização explícita.
