# Roadmap macro

Este roadmap registra a direção atual do AI Service Desk. Ele não é backlog detalhado e não congela o desenho das fases futuras. Cada fase recebe sua própria especificação, critérios de saída e plano antes da implementação.

A arquitetura aprovada para Policy Engine, aprovação, execução controlada e CDM está registrada em `docs/architecture/2026-09-08-policy-execution-cdm-handoff.md`. Esse documento é a fonte canônica para as decisões das Fases 7 a 10 e deve ser lido antes da spec da Fase 7.

| Fase | Objetivo |
| --- | --- |
| 0 | Fundação do repositório |
| 1 | Motor atual reproduzível |
| 2A | Retrieval demonstrável para a competição em subset real determinístico |
| 2B | Validação de escala no corpus completo de 15.542 tickets |
| 3 | Avaliação e calibração |
| 4 | FAQ e base de conhecimento |
| 5 | Triagem conversacional |
| 6 | Playbooks |
| 7 | Policy Engine e contexto de solicitação |
| 8 | Aprovação e execução controlada |
| 9 | Integração CDM |
| 10 | Roteamento e escalonamento |
| 11 | Aprendizado e prevenção |
| 12 | Interface web e demonstração final |

## Regra de progressão

O projeto não avança apenas porque uma fase parece funcional. A transição exige evidência compatível com os critérios mensuráveis definidos na especificação da fase em execução.

Para a competição, a Fase 2A é o gate de retrieval. Após sua homologação, o trabalho de produto pode seguir para as fases seguintes sem aguardar a conclusão da Fase 2B.

A Fase 2B continua válida como evidência adicional de escala, integridade e retomada do índice completo. Ela não substitui a avaliação e calibração estatística da Fase 3.

## Fase 3: regra de calibração

A Fase 3 usa um benchmark sintético versionado para regressão e um sweep reproduzível de thresholds. Essas métricas não representam precisão, recall, cobertura ou taxa de automação sobre os 240 tickets da demo ou sobre o corpus completo de 15.542 tickets.

O threshold de runtime permanece em `0.65` por decisão `HOLD` enquanto não existir um gold set corporativo real rotulado por humanos. Uma recomendação derivada apenas do benchmark sintético não altera o comportamento de produção.

A saída da Fase 3 exige CI hospedado verde, hard gates de segurança zerados no threshold oficial, homologação no runner Dell com os modelos locais e revisão final do PR.

## Direção aprovada para as Fases 7 a 10

### Fase 7. Policy Engine e contexto de solicitação

Responsabilidades:

- identidade confiável via `SessionIdentity` ou contrato equivalente;
- preparação de `AccessRequestContext`;
- normalização segura de role do CDM;
- pedido genérico de acesso sem indicação de privilégio normaliza para `SOLICITANTE`;
- `SOLICITANTE -> REQUIRE_APPROVAL`;
- `APROVADOR -> DENY`;
- `ADMIN -> DENY`;
- `SUPERADMIN -> DENY`;
- `PolicyDecision` determinística e fail-closed;
- `ConfidenceAssessment` separado da autorização;
- nenhum LLM decide autorização;
- nenhuma chamada ao CDM.

### Fase 8. Aprovação e execução controlada

Responsabilidades:

- entidade/registro de solicitação;
- máquina de estados;
- `PENDING_APPROVAL`;
- aprovação e rejeição humana;
- checagem de autorização do técnico;
- revalidação de policy;
- auditoria;
- Execution Engine com executor fake inicialmente.

### Fase 9. Integração CDM

Responsabilidades:

- API local simulada do CDM;
- `CDMAdapter`;
- service credential simples;
- consulta de acesso;
- criação de acesso `SOLICITANTE`;
- idempotência;
- tratamento de erros;
- integração do Execution Engine ao adapter.

A API real deve substituir somente a implementação do adapter, sem alterar Policy Engine, Playbooks ou regras de negócio.

### Fase 10. Roteamento e escalonamento

Responsabilidades:

- configuração mínima de técnicos e capacidades;
- `CDM -> técnico CDM`;
- encaminhamento automático de solicitações permitidas;
- fila de aprovação;
- `DENIED_POLICY` fora da fila operacional;
- domínios adicionais apenas para demonstrar responsáveis distintos.

## Decisões congeladas da primeira demonstração

- CDM é a única integração externa executável.
- A plataforma hospedeira fornece a identidade do usuário.
- O ambiente local usa identidades simuladas.
- Não será criado um sistema de autenticação paralelo.
- Os roles do CDM são `SOLICITANTE`, `APROVADOR`, `ADMIN` e `SUPERADMIN`.
- Pedido genérico de acesso ao CDM, sem indicação de privilégio, usa `SOLICITANTE`.
- Somente `SOLICITANTE` pode seguir para aprovação humana.
- `APROVADOR`, `ADMIN` e `SUPERADMIN` são proibidos pelo canal do agente.
- Não existe `AUTO_APPROVE`.
- `HIGH` não aprova automaticamente.
- `LOW` não rejeita automaticamente um pedido de `SOLICITANTE`.
- Solicitações bloqueadas por policy continuam auditáveis.
- Aprovação acontece na nossa plataforma.
- O frontend não chama o CDM diretamente.
- O backend revalida policy antes da execução.
- A API simulada será criada antes da integração real.
- HTTP específico do CDM ficará encapsulado em adapter.
- Nenhum outro sistema precisa de integração automática na primeira versão.
