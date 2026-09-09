# Roteiro da demonstração final, Jup Resolve

## Objetivo

Demonstrar que o Jup Resolve reduz solicitações desnecessárias, organiza as que realmente precisam existir e preserva controle humano e regras do backend quando há ação externa.

O roteiro usa somente dados sintéticos e deve ser executado com a demo local já construída.

## 1. Abrir como Pedro

Abra `http://127.0.0.1:8000/` e confirme a identidade demo **Pedro Miranda**.

A superfície inicial deve ser Jup, com saudação, composer e sem dashboard de KPIs.

## 2. Resolver Microsoft 365 por Knowledge

Envie uma mensagem equivalente a:

> Não consigo acessar o Microsoft 365 depois que esqueci minha senha.

Mostre que Jup devolve a orientação APPROVED literalmente e que nenhuma solicitação é criada.

Mensagem-chave para a apresentação: o primeiro ganho do produto é evitar que um chamado exista quando Knowledge suficiente já resolve o problema.

## 3. Solicitar acesso ao CDM

Envie:

> Preciso de acesso ao CDM para solicitar materiais para uma revenda.

O backend deve criar uma solicitação real e retornar `PENDING_APPROVAL`.

## 4. Mostrar “O que entendi”

Use o painel **O que entendi** para explicar os dados estruturados recebidos do backend:

- Sistema: CDM;
- intenção/solicitação identificada;
- finalidade;
- Confidence como evidência de classificação, não como aprovação;
- decisão de Policy;
- próxima etapa.

Não apresente Confidence como autorização ou sucesso.

## 5. Trocar para Técnico CDM

No seletor de identidade demo, escolha **Técnico CDM**.

A navegação de Operação passa a existir porque o backend informou `can_operate`. Essa visibilidade não substitui autorização no backend.

## 6. Abrir Operação / Pendências

Entre em **Operação > Pendências**.

Mostre que somente a solicitação atribuída ao `TECH-CDM` está disponível e abra o contexto operacional:

- solicitante e área;
- finalidade;
- Policy;
- Confidence;
- Routing;
- timeline real.

## 7. Aprovar

Acione **Aprovar e executar**.

Durante a chamada, a interface deve impedir submissão duplicada e apresentar estado de progresso. A UI não declara sucesso antes da resposta do backend.

## 8. Mostrar a progressão real da execução

Na resposta, destaque os eventos que realmente ocorreram:

```text
REQUEST_APPROVED
EXECUTION_STARTED
EXECUTION_COMPLETED
```

Explique a cadeia:

```text
ApprovalService
-> ExecutionEngine
-> revalidação de Policy
-> CDMActionExecutor
-> CDMAdapter
-> fake CDM
```

O resultado esperado do cenário principal é `CDM_ACCESS_CREATED` e estado final `COMPLETED`.

## 9. Voltar para Pedro

Troque novamente a identidade para **Pedro Miranda** e abra **Solicitações**.

## 10. Mostrar COMPLETED ao solicitante

Abra a solicitação do CDM e destaque o estado **Concluída / COMPLETED** e a timeline recebida do backend.

Mensagem-chave: solicitante e técnico enxergam projeções diferentes do mesmo lifecycle, sem o frontend inventar estados.

## 11. Abrir Operação / Prevenção

Volte para **Técnico CDM** e abra **Operação > Prevenção**.

Mostre a oportunidade recorrente derivada dos outcomes sintéticos do runtime.

## 12. Explicar a recorrência

Explique que a categoria, quantidade de ocorrências e evidências vêm do motor homologado da Fase 11:

```text
OutcomeRecord
-> PatternAggregator
-> OpportunityEngine
-> PreventionOpportunity
```

A UI apenas apresenta essa projeção. Ela não contém limiar de recorrência nem escolhe categoria.

## Fechamento sugerido

O Jup Resolve demonstra três níveis de redução de carga do Service Desk no mesmo fluxo:

1. resolve diretamente quando existe Knowledge APPROVED suficiente;
2. estrutura e encaminha com controle humano quando uma solicitação precisa existir;
3. transforma outcomes recorrentes em oportunidades explicáveis de Prevenção.

O princípio que amarra a demonstração é:

**UI apresenta estado; backend decide estado.**
