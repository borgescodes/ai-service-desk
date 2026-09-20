# Phase 16 — Task 3: experiência conversacional CDM

Baseline: `7a17565ec0cb77a00eb14a02193cd8c95772644d`, branch `phase-16-demo-readiness`.
Execução inline, **GPT-6 Astra / Medium**, sem subagents e sem escalada, conforme override explícito do usuário. Checkpoint: commit que adiciona este handoff (`git log -1 --format=%H -- docs/superpowers/plans/2026-09-20-phase-16-task-3-handoff.md`); SHA também informado no encerramento.

## Contrato entregue

- Pergunta sobre como obter acesso usa a resposta curta aprovada `KB-SYN-CDM-ACCESS-001`, preservada literalmente, referencia o artigo completo `KB-SYN-FAQ-CDM-REQUEST-001` da Central e oferece registrar a solicitação. Não cria pedido.
- O artigo completo permanece inalterado. O chat recebe metadados do catálogo aprovado e apresenta link interno; nenhuma regra de negócio foi movida ao frontend.
- A oferta usa `ConversationContext.dialogue.stage`, sem estado paralelo. Aceitação reutiliza a finalidade original, o texto atual e a identidade confiável. O interpreter também pode reconhecer aceitação sem impor papel ou escopo.
- Resolução de papel/escopo, divergência, policy, aprovação e execução continuam integralmente na Task 2. Financeiro → UBS continua divergente e exige confirmação. `Sim, é para UBS` confirma apenas o escopo pendente, preservando a área da sessão.
- Nova conversa ou turno interveniente encerra a oferta. Uma nova orientação também descarta pendência CDM anterior, impedindo que um `Sim` posterior materialize um pedido antigo.
- Retrieval sem evidência aprovada, artigo ausente, DRAFT ou RETIRED não produzem oferta nem pedido. Provenance e os testes de proteção anteriores permanecem intactos.

## Grounding e decisões

Decisão: reutilizar `ResponseGrounding` / `ProtectedContent` e os slots existentes `intro` / `outro` para o CDM. Orientação, oferta, pergunta pendente e resultado operacional são compostos a partir do conteúdo aprovado e do resultado autoritativo. O writer escolhe conexões breves permitidas; saída fora dessas restrições retorna o conteúdo protegido. Isso fecha o espaço para notificações, técnico, SLA, contato futuro, acompanhamento, procedimentos e status fabricados, sem tentar enumerar todas as paráfrases de alucinação.

Custo deliberado: menor variação de linguagem no CDM. Não foi criada uma arquitetura de prompting nem alterada a linguagem dos demais fluxos. As frases de resultado são curtas e reutilizam o grounding existente. O hardening transversal permanece na Task 7.

Dois testes antigos de integração esperavam texto operacional livre; passaram a exigir os slots protegidos e a mensagem de espera por aprovação. Nenhum teste de autorização, hash, provenance ou policy foi flexibilizado. A regressão de cadastro de material foi corrigida exigindo evidência de acesso antes da orientação CDM.

## Evidências

- TDD: falhas observadas para criação prematura, perda de oferta, confirmação curta, falsas promessas, pendência antiga, retrieval sem provenance e cancelamento/perfil ambíguo sem proteção; implementações verificadas pelos testes correspondentes.
- Testes determinísticos novos incluem as seis aceitações solicitadas, identidade, UBS automático, Financeiro sem escopo, seleção curta, divergência, confirmação, oferta expirada, DRAFT/RETIRED/ausência, tentativa de atribuir papel/escopo pelo modelo e vinte combinações de alegações falsas em criação/pendência.
- Ollama real: `qwen3.5:4b` e `qwen3-embedding:0.6b`, `LOCAL_AI`, duas baterias A–D aprovadas, respectivamente **4 passed / 151,86 s** e **4 passed / 143,78 s**. Sem substituição das inferências.
- A: UBS recebeu orientação + artigo + oferta; aceitação criou solicitante/UBS em `PENDING_APPROVAL`.
- B: Financeiro não recebeu escopo inventado; `UBS` abriu confirmação de divergência; confirmação criou o pedido preservando Financeiro.
- C: Revenda → UBS exigiu confirmação e manteve Revenda como área confiável.
- D: pedido contendo instruções para inventar notificação, contato, acompanhamento, aprovação e liberação retornou somente criação confirmada e espera por aprovação. A–C foram aprovados pelo técnico e chegaram a `COMPLETED` no fake; o primeiro criou acesso, os seguintes reconheceram acesso existente para o mesmo e-mail/escopo. Nenhuma resposta conversacional prometeu esses efeitos antecipadamente.
- Logs diagnósticos locais: `reports/task3/ollama.txt`, `reports/task3/ollama-final.txt` e relatórios pytest, todos ignorados pelo Git.
- Frontend: **122 testes**, lint e build aprovados. Exercício adicional do renderer do chat confirmou o link navegável para o artigo aprovado. Não houve inspeção visual em navegador.
- Ruff check, Ruff format --check e `git diff --check`: aprovados.
- `python -m pytest`: **1346 passed, 31 skipped**, 76 avisos preexistentes de depreciação FastAPI/Starlette, 195,68 s. Os skips são homologações opt-in; os quatro novos casos Ollama foram executados separadamente e passaram. Tasks 1 e 2 e contratos de segurança passaram na suíte completa.

Para repetir a homologação em PowerShell, configure `PYTHONPATH` para o `src` deste checkout e `JUP_CDM_LOCAL_QA=1`; execute `python -m pytest tests/web/test_cdm_local_acceptance.py -q -s`. O Python global pode resolver o checkout do runner sem `PYTHONPATH`, conforme evidência da Task 2.

## Arquivos alterados

- `src/ai_service_desk/web/conversation.py`
- `src/ai_service_desk/web/conversation_grounding.py`
- `src/ai_service_desk/web/conversation_interpreter.py`
- `src/ai_service_desk/web/demo_runtime.py`
- `tests/web/test_cdm_conversation.py`
- `tests/web/test_cdm_local_acceptance.py`
- `tests/web/test_demo_local_ai.py`
- `web/src/app.mjs`
- `web/src/components.mjs`
- `web/src/knowledge_content.mjs`
- `web/tests/knowledge-content.test.mjs`
- Este handoff.

## Limitações e próxima task

Mantidos o catálogo, o reconhecimento de escopo e a heurística de confiança da Task 2. Formulações de finalidade que aquele contrato considera área desconhecida continuam pedindo esclarecimento; não se fez aproximação nem redesenho de escopo. A confirmação semântica da oferta exige oferta ativa; a confirmação do escopo usa as formas delimitadas e o catálogo autoritativo. Revisão realizada inline, sem segundo revisor, por instrução explícita do usuário.

Sem API produtiva CDM, persistência, polish ou implementação das Tasks 4–9. `jup-apresentation` não foi lida nem alterada. Nenhum push, PR, merge ou alteração de main.

Recomendação para Task 4: **GPT-5.6 Sol / Medium**, para o fluxo M365 e segundo artigo sobre contratos existentes; Astra / Medium somente se surgir ambiguidade concreta de autoridade/grounding.

Status: **PASS**. Nenhum critério foi flexibilizado para obter verde. Working tree deve ficar limpo após o checkpoint local.
