# Fase 13 — Experiência do Solicitante e Redesign Visual

## 1. Objetivo

A Fase 13 substitui a aparência atual de "frontend de IA" por uma experiência própria da Juparanã, orientada ao solicitante e composta por duas portas de entrada:

```text
Solicitante
    |
    +--> Soluções / FAQ
    |
    +--> Falar com o Jup
```

O objetivo não é adicionar novas decisões de negócio. É reorganizar a experiência, criar uma porta de autoatendimento baseada em Knowledge APPROVED, tornar a conversa com o Jup uma interface dedicada e elevar a qualidade visual da demonstração.

A Fase 12 homologada permanece a referência funcional. O redesign não reabre Policy, routing, approval, execution, CDM, triage, learning/prevention ou regras do agente.

## 2. Baseline obrigatório

Base exata:

```text
96d88ed58df5e2d007aedd8cbed2f2c779750e05
```

Esse SHA é o candidate homologado da Fase 12, com gates locais e GitHub Actions aprovados.

A execução desta fase deve acontecer em nova branch/worktree, sugerida:

```text
phase-13-requester-experience
```

Não modificar a branch `phase-12-web-demo`, o Draft PR #15 ou o SHA homologado.

## 3. Modo da superfície

Impeccable mode:

```text
Operate
```

O usuário chega para resolver um problema de TI. Scanabilidade, rapidez, estado e clareza vencem expressão decorativa.

A interface não deve fazer marketing de si mesma. A capacidade do produto deve ficar evidente pelo uso.

## 4. Público e escopo

Público principal:

```text
solicitante / colaborador Juparanã
```

A experiência pública não possui login real, SSO ou seletor de identidade visível.

Identidade demo pública padrão:

```text
pedro-miranda
```

A visão técnica existe apenas para demonstrar o que ocorreu por trás da triagem/encaminhamento. Ela deve continuar acessível por rota dedicada, mas não aparece na navegação pública.

## 5. Não objetivos

Não fazem parte desta fase:

```text
mobile
tablet
PWA
novo auth
SSO
novo RBAC
mudança em Policy
mudança em routing
mudança em approval
mudança em execution
mudança em CDM
mudança no comportamento conversacional homologado
novas integrações externas
analytics
telemetria nova
framework frontend
React
Vue
Svelte
Vite
dependências npm de runtime
CDN
fontes externas
copy de marketing
homepage institucional
landing page
hero comercial
cards de KPI
chat flutuante genérico
glassmorphism
gradients “AI”
glow
chat bubbles decorativas em excesso
pills em excesso
ícones em quadrados coloridos genéricos
```

A fase é desktop-only. Não gastar tempo de projeto, implementação ou QA em mobile/tablet.

## 6. Princípios invioláveis

```text
LLM entende e conversa. Backend decide e executa.
UI apresenta estado; backend decide estado.
```

Também são obrigatórios:

1. Frontend nunca decide Policy, routing, approval ou execution.
2. Frontend nunca chama CDM.
3. Texto digitado pelo usuário nunca altera identity.
4. Somente Knowledge `APPROVED` pode virar orientação pública.
5. `DRAFT`, `RETIRED` e `HISTORICO_NAO_VALIDADO` nunca aparecem como resposta oficial.
6. Resposta de FAQ é literal do campo `answer`; frontend não reescreve procedimento.
7. URLs vindas de texto/Knowledge não viram links arbitrariamente.
8. O link Microsoft aprovado continua exatamente:

```text
https://mysignins.microsoft.com/security-info/password/change
```

9. O candidate da Fase 12 continua preservado.
10. Sem force push, merge, Ready for Review ou delete de branch sem autorização explícita.

## 7. Fonte e contrato da FAQ

### 7.1 Fonte de demanda

A base histórica indicada pelo usuário:

```text
https://drive.google.com/file/d/1GdzcOMFVOfND_6zzKyCOEPNxaaxcxlUG/view?usp=sharing
```

serve para priorizar temas e identificar recorrência.

Ela não é uma fonte de orientação oficial. Os registros históricos estão marcados como `HISTORICO_NAO_VALIDADO`; portanto o Codex não pode copiar solução histórica e promovê-la para `APPROVED` por iniciativa própria.

### 7.2 Evidência de priorização já levantada

A base mostra forte recorrência em famílias como:

```text
SIAGRI
CIGAM
Microsoft 365 / Outlook / OneDrive / Teams
Impressoras / equipamentos
```

CDM continua importante para a demonstração do agente, mas não deve ocupar uma categoria de FAQ artificialmente se o corpus aprovado não justificar isso.

### 7.3 Fonte de resposta pública

A FAQ deve projetar apenas conteúdo já aprovado das fontes existentes no repositório e da Knowledge sintética da demo, sem alterar o schema core da Fase 4.

Fontes iniciais permitidas:

```text
knowledge/phase4_synthetic_faq.jsonl
Knowledge sintética escrita por src/ai_service_desk/web/demo_data.py
```

O runtime conversacional continua usando a Knowledge específica da demo como hoje. A FAQ pode combinar fontes APPROVED para navegação sem ampliar automaticamente o índice conversacional da Fase 12.

### 7.4 Limites de apresentação

```text
máximo de 16 soluções expostas
máximo de 4 categorias destacadas
máximo de 4 soluções por categoria destacada
```

A interface deve funcionar corretamente com 1 a 16 soluções e 1 a 4 categorias. Não criar conteúdo fake para preencher grade.

Categorias destacadas preferenciais, quando houver artigos APPROVED compatíveis:

```text
SIAGRI
CIGAM
Microsoft 365
Equipamentos e impressão
```

Artigos APPROVED fora dessas famílias podem aparecer na busca sem obrigar uma quinta coluna na home.

## 8. Contrato HTTP da FAQ

Criar boundary HTTP fina sob `src/ai_service_desk/web/`.

### `GET /api/faq`

Retorna somente grupos destacados e metadados seguros de artigos APPROVED.

Shape:

```json
{
  "groups": [
    {
      "key": "siagri",
      "label": "SIAGRI",
      "items": [
        {
          "knowledge_id": "KB-SYN-SIAGRI-ACCESS-001",
          "title": "Acesso sintético ao SIAGRI",
          "question": "Não consigo acessar o SIAGRI no ambiente fictício.",
          "system": "SIAGRI",
          "category": "SIAGRI"
        }
      ]
    }
  ],
  "total": 1
}
```

Regras:

- máximo 4 grupos;
- máximo 4 itens por grupo;
- não retornar `DRAFT`/`RETIRED`;
- não retornar `reviewed_by`, `reviewed_at`, `source` ou campos internos desnecessários;
- endpoint não requer identity.

### `GET /api/faq/search?q=<texto>`

Busca lexical determinística sobre a projeção APPROVED.

Campos pesquisáveis:

```text
title
question
system
category
tags
```

Regras:

- case-insensitive;
- accent-insensitive;
- ordenação determinística;
- até 16 resultados;
- sem LLM;
- sem embedding;
- sem chamada Ollama;
- sem fallback para histórico bruto.

Shape:

```json
{
  "items": [
    {
      "knowledge_id": "...",
      "title": "...",
      "question": "...",
      "system": "...",
      "category": "..."
    }
  ],
  "total": 1
}
```

### `GET /api/faq/{knowledge_id}`

Retorna detalhe seguro de um artigo APPROVED:

```json
{
  "knowledge_id": "...",
  "title": "...",
  "question": "...",
  "answer": "...",
  "system": "...",
  "category": "...",
  "procedure_url": null
}
```

Para `KB-SYN-M365-PASSWORD-001`, `procedure_url` pode ser somente:

```text
https://mysignins.microsoft.com/security-info/password/change
```

Nenhuma URL arbitrária deve ser promovida a anchor.

## 9. Arquitetura de rotas

### Público

```text
/                     -> soluções / FAQ
/jup                  -> conversa com Jup
/solucoes/<id>        -> leitura de uma solução APPROVED
/requests             -> rota de compatibilidade/deep link, sem item na nav principal
```

### Operacional oculto

Manter visão operacional fora da navegação pública.

Rotas sugeridas:

```text
/demo/operacao/cdm
/demo/operacao/m365
/demo/operacao/prevention
```

Aliases antigos podem ser preservados para não quebrar regressões:

```text
/operations
/operations/prevention
```

A rota dedicada resolve uma identity demo allowlisted; não existe seletor visível na UI pública.

## 10. Header público

O header público deve conter somente:

```text
Jup Resolve                       Soluções   Falar com o Jup
```

Não exibir:

```text
Identidade demo
Operação
Prevenção
Assistente de IA da Juparanã
Inteligência para o Service Desk
qualquer slogan
```

Não inventar logotipo Juparanã se o asset oficial não estiver disponível. Texto simples e bem composto é preferível a marca falsa.

## 11. Home — Soluções

Primeiro viewport desktop:

```text
┌────────────────────────────────────────────────────────────────────┐
│ Jup Resolve                              Soluções  Falar com o Jup │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│ Como podemos ajudar?                                               │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Pesquise por um problema, sistema ou dúvida...              │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ SIAGRI        CIGAM        MICROSOFT 365       EQUIPAMENTOS        │
│ ───────       ─────        ─────────────       ────────────        │
│ solução       solução      solução             solução             │
│ solução       solução      solução             solução             │
│ solução       solução      solução             solução             │
│ solução       solução      solução             solução             │
│                                                                    │
│ ────────────────────────────────────────────────────────────────   │
│ [Jup idle]   Não encontrou o que precisa?      Falar com o Jup → │
└────────────────────────────────────────────────────────────────────┘
```

Características:

- `Como podemos ajudar?` é título funcional, não hero de marketing;
- busca é o controle dominante;
- categorias são listas editoriais, não cards flutuantes;
- usar separadores, hierarquia tipográfica e espaço;
- não usar ícones decorativos para cada tópico;
- área final do Jup pode usar grande campo verde e amarelo com parcimônia;
- copy da área final deve ser somente `Não encontrou o que precisa?` + `Falar com o Jup`.

## 12. Busca dinâmica

A busca deve responder durante digitação com debounce curto, sem botão "Buscar" obrigatório.

Estado de resultado:

```text
3 soluções encontradas

CIGAM
CIGAM não abre após o login
Acesso
────────────────────────────

CIGAM abre em tela azul
Acesso
────────────────────────────
```

Estado vazio:

```text
Nenhuma solução encontrada.
Falar com o Jup →
```

Sem textos promocionais ou explicações longas.

## 13. Leitura de solução

A solução abre como página/estado próprio, nunca modal.

```text
← Todas as soluções

CIGAM
CIGAM não abre após o login

[answer literal APPROVED]

────────────────────────────
Resolveu?
[ Sim ]                         [ Ainda preciso de ajuda → ]
```

Regras:

- `answer` é literal e escapado;
- preservar parágrafos e passos numerados;
- link Microsoft somente quando `procedure_url` corresponder exatamente à allowlist;
- `Sim` não inventa persistência nem aprendizado nesta fase;
- `Ainda preciso de ajuda` navega para `/jup?from=<knowledge_id>`;
- o contexto pode ser exibido na UI do chat (`Você estava vendo: <título>`), mas nesta fase não deve alterar automaticamente triage/domain behavior. O usuário declarou que outros ajustes funcionais serão tratados depois da correção visual.

## 14. Chat dedicado

O chat deixa de ser a home.

Estado inicial:

```text
← Soluções                                      Jup Resolve

                         [Jup]

                  Como posso ajudar?

────────────────────────────────────────────────────────────
│ Descreva o que aconteceu...                        Enviar │
────────────────────────────────────────────────────────────
```

Depois da primeira mensagem, a conversa assume foco.

Remover da experiência pública:

```text
painel permanente “O que entendi”
confidence como KPI visual permanente
policy visível
routing visível
IDs técnicos
slogans
explicação do que o Jup faz
```

Contexto estruturado pode aparecer somente quando útil e em formato compacto, por exemplo:

```text
Microsoft 365 · problema de acesso
```

ou:

```text
Acesso ao CDM · aguardando aprovação
```

A UI nunca recalcula esse estado; apenas traduz estado estruturado já vindo do backend.

## 15. Visual do Jup e motion

O visual do Jup deve ser tratado como linguagem de estado do atendimento, não como mascote decorativo.

Estados já definidos no pacote fornecido pelo usuário:

```text
idle
listening
thinking
success
warning
escalation
```

Sem rosto no warning; warning é um emote/interface state.

Mapping de apresentação:

```text
home disponível                     -> idle
composer focado / usuário interage  -> listening
request HTTP em andamento           -> thinking
resolução confirmada pelo backend   -> success
negação/erro/bloqueio               -> warning
encaminhamento humano               -> escalation
```

O mapping é puramente visual. Ele não decide estado de negócio.

Motion:

- transições de UI: aproximadamente 150–250 ms;
- troca de estado do Jup: aproximadamente 300–450 ms;
- sem entrada coreografada da página;
- sem fade-up em cada seção;
- sem hover que pula;
- sem animação contínua chamativa;
- `prefers-reduced-motion` deve reduzir/desabilitar movimento não essencial.

### Dependência de asset

O pacote refinado do Jup é uma entrada obrigatória para integração final.

Se o asset não estiver disponível no workspace do Codex:

1. implementar o contrato de estado e o container visual;
2. não inventar outro avatar;
3. não gerar mascote genérico;
4. parar antes de substituir o visual atual e reportar a dependência ausente.

## 16. Direção visual Juparanã

Cores oficiais fornecidas:

```text
Verde   #45813C
Amarelo #EEB41E
Cinza   #808285
Branco  #FFFFFF
```

Estratégia de cor:

```text
Full palette controlada / Operate
```

Uso:

- verde: estrutura, header ativo, áreas institucionais e CTA Jup;
- amarelo: estado/ênfase pontual, nunca cor de preenchimento espalhada;
- cinza: informação secundária e divisores;
- branco: superfície de leitura;
- preto/ink neutro para texto.

Não usar gradient.

## 17. Forma, layout e tipografia

Desktop de referência:

```text
1280–1600 px de largura
1440x900 como captura principal
```

Não desenhar breakpoint mobile.

Direção:

- content width aproximada: 1180–1240 px;
- header compacto, sem três zonas de dashboard;
- h1 funcional, não oversized;
- busca ampla e central, mas não hero comercial;
- FAQ em 4 colunas editoriais quando houver 4 categorias;
- poucas bordas arredondadas;
- radius pequeno/médio;
- sombras quase inexistentes;
- linhas e ritmo substituem card grid;
- sistema tipográfico local/system stack; não adicionar font externa;
- foco visível e contraste preservados.

## 18. Área operacional

A visão técnica continua existindo para a apresentação, mas fica fora da navegação pública.

Ela continua mostrando o backend real:

```text
triagem
solicitação
policy
routing
approval
execution
prevention
```

Nenhuma regra operacional deve migrar para frontend.

O redesign público não exige redesenhar profundamente a área operacional nesta fase; é suficiente mantê-la funcional, discreta e acessível por rota dedicada.

## 19. Arquivos core protegidos

Não modificar:

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/request_lifecycle.py
src/ai_service_desk/engine/request_repository.py
src/ai_service_desk/engine/approval.py
src/ai_service_desk/engine/execution.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
```

Também evitar alteração em core de Knowledge. A FAQ deve usar `load_knowledge()` e `approved_articles()` como contratos existentes, encapsulada na application layer web.

**Exceção cirúrgica autorizada em 13/09/2026:** o handoff de correção Windows permite alterar somente o transporte de `integrations/cdm_fake_api.py` para consumir o corpo declarado de POST não autorizado antes do 401. O blob autorizado passa de `275b1833d5b27b09c0ffeae9f4484636d10afe63` para `790a3d3fb13bd3b617c0e8587811bf70e519e40c`. A exceção inclui o teste determinístico de regressão e a atualização exata dos gates desse blob; todos os demais arquivos protegidos permanecem preservados. Não muda autenticação, status/error_code, adapter real, policy, lifecycle ou execução. Evidências e resultados constam em `docs/demo/phase-13-requester-experience.md`.

## 20. Critérios de aceitação

A fase só está aceita quando:

```text
/ abre FAQ/Soluções, não chat
/jup abre chat dedicado
header público não mostra identity/Operação/Prevenção
FAQ mostra somente APPROVED
DRAFT/RETIRED nunca aparecem
busca é dinâmica e determinística
máximo 16 resultados
máximo 4 grupos destacados
solução abre em página própria
answer APPROVED permanece literal
link Microsoft continua allowlisted e correto
Ainda preciso de ajuda leva ao Jup
chat continua entregando os 6 fluxos F12 homologados
CDM normal continua PENDING_APPROVAL
CDM admin continua DENY
M365 password continua procedimento correto
M365 success continua resolvido
M365 failure continua handoff
out-of-scope continua redirecionado
nenhum core protegido mudou
nenhum decision rule foi movido ao browser
visual usa #45813C / #EEB41E / #808285
sem marketing self-referential
sem visual de dashboard SaaS genérico
Jup usa estados visuais reais quando asset disponível
frontend lint/test/build passa
full pytest passa
node IDs históricos continuam preservados
security gates F8–F12 passam
smokes routing / learning-prevention / web-demo passam
```

## 21. Handoff de implementação

O executor deve usar TDD estrito:

```text
RED -> GREEN -> REFACTOR -> commit
```

Usar `superpowers:subagent-driven-development` como primeira opção ou `superpowers:executing-plans` inline.

Antes de qualquer UI edit, usar Impeccable no worktree e respeitar esta direção como já aprovada. Não reabrir um torneio estético para o usuário. Usar Impeccable para craft floor, motion, color, inspeção e finish review.

Não fazer push, merge, Ready for Review ou delete de branch sem autorização explícita.
