# Fase 13 — roteiro do solicitante

A experiência começa pela FAQ APPROVED. A conversa mantém as decisões homologadas da Fase 12. Todos os dados da demonstração são sintéticos.

## Rotas

| Rota | Uso | Identidade demo |
|---|---|---|
| `/` | Soluções / FAQ e busca dinâmica | pedro-miranda |
| `/jup` | Conversa dedicada | pedro-miranda |
| `/solucoes/<knowledge_id>` | Leitura literal de solução aprovada | pedro-miranda |
| `/requests` | Deep link de solicitações | pedro-miranda |
| `/demo/operacao/cdm` | Operação CDM | tecnico-cdm |
| `/demo/operacao/m365` | Operação Microsoft 365 | tecnico-m365 |
| `/demo/operacao/prevention` | Prevenção | tecnico-geral |

Os aliases `/operations` e `/operations/prevention` continuam disponíveis. As rotas operacionais ficam fora da navegação pública. Não há autenticação real: as identidades são exclusivamente da demo, fixadas por rota e validadas pela allowlist do backend. Query strings e texto do chat não escolhem a identidade.

## Apresentação

```powershell
npm --prefix web test
npm --prefix web run lint
npm --prefix web run build
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000 --mode LOCAL_AI
```

Ollama deve disponibilizar `qwen3.5:4b`. O modo `DETERMINISTIC` segue disponível para testes reproduzíveis; para o roteiro conversacional completo use `LOCAL_AI`.

1. Abra `/`, digite parte de um problema ou sistema e escolha uma solução. A busca não altera a ordem calculada pelo backend.
2. Leia a solução. “Sim” volta à home, sem persistência ou aprendizado. “Ainda preciso de ajuda” abre `/jup?from=<knowledge_id>`; o título é apenas contexto visual, não é enviado automaticamente ao agente.
3. No chat, use “Esqueci minha senha do Microsoft 365.”. Confirme os sete passos e o link Microsoft exato.
4. Responda “funcionou” para resolução; em uma sessão reiniciada, repita o procedimento e responda “não funcionou” para encaminhamento ao especialista Microsoft 365.
5. Em sessão reiniciada, solicite acesso normal ao CDM: estado PENDING_APPROVAL, sem execução antes de aprovação.
6. Em sessão reiniciada, solicite admin no CDM: DENY, sem execução. Pergunta fora do escopo retorna orientação de atendimento de TI.

O resumo técnico do encaminhamento pode ser aberto pelo solicitante, sem poluir a leitura principal. Policy, confidence e IDs não são adicionados como painel público; mensagens e resumos literais recebidos do backend permanecem intactos.

## Fonte da FAQ

`knowledge/phase4_synthetic_faq.jsonl` e a Knowledge sintética gerada por `web/demo_data.py` alimentam somente a projeção web. O índice conversacional não foi ampliado. A home atual possui cinco artigos em quatro categorias; não foram criados artigos para preencher a grade.

Busca lexical determinística, insensível a caixa e acentos, com até 16 resultados. Destaques limitados a quatro categorias e quatro itens por categoria. DRAFT e RETIRED não são publicados. Histórico bruto não entra no catálogo.

O conteúdo é escapado. URLs em texto permanecem texto; somente `https://mysignins.microsoft.com/security-info/password/change` pode gerar link, conforme o campo seguro do backend.

## Origem do Jup

Pacote local fornecido: `jup-avatar-animated-final-v7-transition-final.zip`, versão final mais recente encontrada em Downloads. Os seis estados foram normalizados diretamente de `JupFace.tsx` para módulos com a geometria SVG original. `jup-no-face.png` foi copiado sem alterar pixels ou metadados. Nenhum avatar foi gerado ou baixado como substituto.

A adaptação remove React/Vite, usa caminhos locais, troca gradientes CSS por superfície sólida e limita o movimento conforme a spec. Warning mantém somente o triângulo de alerta, sem olhos ou boca. `jup_visual_assets.mjs` centraliza as referências. O manifesto de proveniência e os hashes da inspeção ficam nos artefatos locais.

SHA-256 do PNG original e da cópia versionada: `5e72759d1ac148232f6475ed3aea62f5b8962167ee95aed71db92afffe6cb7e7`.

## Verificação local

Evidências da execução ficam em `artifacts/phase13-*` e `artifacts/phase13-review/`, fora do Git. O ledger de execução inline fica em `.superpowers/sdd/2026-09-12-phase-13-requester-experience/`.

O comando de routing existente é `python -m ai_service_desk routing-escalation-smoke` (o nome abreviado `routing-smoke` no plano não existe). Os outros smokes são `learning-prevention-smoke` e `web-demo-smoke`.

No Windows, o CSV sintético `tests/fixtures/phase2_corpus.csv` deve manter os bytes LF do blob Git para preservar o hash bruto esperado. A conversão automática para CRLF não é mudança de produto; não atualizar o manifesto para acomodá-la.

Resultado local em 12/09/2026:

| Verificação | Resultado |
|---|---|
| Pytest completo | 1166 passaram, 3 skips existentes, 1 falhou |
| Frontend | 59 testes passaram; lint e build passaram |
| Ruff | Check e format check passaram |
| Histórico | 925 node IDs preservados; nenhum ausente |
| Core protegido | Diff vazio contra o candidate F12; 19 blobs do guard histórico preservados |
| Routing / learning-prevention / web-demo | 8/8, 10/10 e 10/10 |
| LOCAL_AI com Qwen local | 6/6 cenários conversacionais passaram |
| Impeccable | Revisão inline desktop em 1280, 1440×900 e 1600; detector sem achados |

**Bloqueio registrado em 12/09:** `tests/integrations/test_cdm_fake_api.py::test_post_requires_bearer` falhou com `WinError 10053` na execução completa. A repetição isolada dos dois módulos CDM passou (33 testes), sem substituir o gate completo. O mesmo tipo de aborto de conexão já havia sido observado no baseline, em `test_create_maps_401_to_auth_error`. A correção autorizada e sua nova verificação estão descritas abaixo.

Superfícies conferidas no navegador: home nas três larguras, busca com resultado e vazia, solução Microsoft 365, chat vazio, contexto de artigo, procedimento real com sete passos e URL permitida, handoff com resumo recolhido/expansível e navegação operacional Microsoft 365. Contraste medido de texto branco sobre verde: 4,71:1.

A implementação deve permanecer local até autorização explícita de push. Não houve alteração da branch Fase 12, do Draft PR #15, merge ou Ready for Review.

## Correção de transporte Windows — 13/09/2026

O handoff `phase-13-cdm-windows-fix-handoff-codex-inline.md`, fornecido para continuar a execução, autorizou uma exceção cirúrgica à seção 19 da spec. O único arquivo de produção alterado nesta correção é `src/ai_service_desk/integrations/cdm_fake_api.py`.

O caminho de autenticação inválida enviava 401 antes de consumir o corpo POST. O experimento reportado no handoff fez 100 requisições por cenário: sem body, 100 respostas 401 e zero abortos; JSON pequeno, 91 respostas e 9 abortos; JSON grande, 92 respostas e 8 abortos. Nesta execução, um teste determinístico confirmou diretamente o diferencial: o handler real começava a resposta com os bytes do body ainda pendentes.

A correção descarta o número de bytes declarado em `Content-Length`, em blocos de até 64 KiB, antes do 401. Não interpreta JSON no caminho não autorizado, não persiste dados e não inclui body ou credenciais na resposta. Comprimentos ausentes, inválidos ou não positivos não provocam leitura ilimitada; EOF encerra o descarte. O caminho autenticado e o adapter real permanecem intactos. Sem bearer ou com bearer errado, a resposta continua `401 / CDM_SERVICE_UNAUTHORIZED`.

TDD inline: quatro casos novos falharam por consumo ausente antes da resposta (body não JSON e body grande, com bearer ausente ou errado). Após a mudança mínima, esses quatro casos e quatro guardas de comprimento passaram. O teste executa o handler HTTP real com uma conexão em memória observável; verifica consumo antes da primeira escrita e preservação de bytes posteriores ao body. Não depende de tentar a requisição repetidamente até reproduzir um reset. Não foram adicionados retries, skips, aumento de timeout ou tratamento que esconda `WinError 10053`.

Blob anterior: `275b1833d5b27b09c0ffeae9f4484636d10afe63`. Blob autorizado: `790a3d3fb13bd3b617c0e8587811bf70e519e40c`. Os gates F10/F11 mantêm os parâmetros e node IDs históricos, aplicando somente a exceção exata do fake CDM. Para esse arquivo, validam também o conteúdo do worktree antes do commit; os workflows F10–F12 continuam verificando o blob exato de HEAD. Todos os demais blobs permanecem preservados.

Os comandos Python foram executados com `PYTHONPATH` resolvido para `src` deste worktree. Ambiente: Python 3.14.7, Ruff 0.12.12 e Node 26.7.0. As evidências novas ficam em `artifacts/phase13-cdm-*`; o roteiro LOCAL_AI reutiliza `artifacts/phase13-local-ai-smoke.py` da execução anterior.

Verificação final em 13/09/2026, após a correção:

| Gate | Resultado |
|---|---|
| RED / GREEN determinístico | 4 falhas por body não consumido → 8 casos passaram |
| Integrações | 55 passaram |
| Engine CDM, segurança F10/F11 e workflow F12 | 64 passaram |
| Workflows F10–F12 | 6 testes passaram; sintaxe dos 5 blocos Python embutidos válida |
| Pytest completo | **1175 passaram, 3 skips existentes, zero falhas**, 128,32 s |
| Ruff | Check e format check passaram; 162 arquivos formatados |
| Frontend | 59 testes, lint e build passaram |
| Routing / learning-prevention / web-demo | 8/8, 10/10 e 10/10 |
| LOCAL_AI com Qwen local | 6/6 cenários passaram |
| Histórico | 925 IDs preservados; 1178 candidatos; zero ausentes |
| Blobs protegidos | 19 verificações passaram; somente a exceção exata do fake CDM |

O primeiro full suite desta correção passou pelo transporte CDM e encontrou uma falha no guard histórico do workflow F11. O workflow foi ajustado para manter o hash histórico e aplicar o hash autorizado em `expected.update`, seguindo o padrão existente. A execução completa final acima passou. Os três skips são a QA explicitamente opt-in de contexto de negócio; o roteiro LOCAL_AI separado foi executado e passou. Nenhum teste foi removido, afrouxado ou pulado para fechar o gate.

O bloqueio local da Fase 13 está encerrado. A homologação remota e qualquer push, merge ou Ready for Review continuam sujeitos à autorização explícita; nenhum desses passos foi executado.
