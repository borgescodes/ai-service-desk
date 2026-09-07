# Roadmap macro

Este roadmap registra a direção atual do AI Service Desk. Ele não é backlog detalhado e não congela o desenho das fases futuras. Cada fase recebe sua própria especificação, critérios de saída e plano antes da implementação.

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
| 7 | Policy engine |
| 8 | Execução controlada |
| 9 | Integrações de sistemas |
| 10 | Escalonamento e roteamento |
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
