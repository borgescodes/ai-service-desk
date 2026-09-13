# Phase 13 Execution Handoff

Este arquivo resolve o estado do repositório **depois** da criação remota da branch e dos documentos de planejamento.

## Autoridade

Ler nesta ordem:

1. `docs/superpowers/specs/2026-09-12-phase-13-requester-experience-design.md`
2. `docs/superpowers/plans/2026-09-12-phase-13-requester-experience.md`
3. este handoff para o estado Git já preparado

A spec é autoridade de produto/UX/arquitetura. O implementation plan é autoridade de execução. Este handoff substitui **somente** as instruções de preflight que mandam criar a branch ou exigir HEAD igual ao candidate da Fase 12.

## Estado Git já preparado

A branch remota já existe:

```text
phase-13-requester-experience
```

Ela foi criada diretamente a partir do candidate homologado:

```text
96d88ed58df5e2d007aedd8cbed2f2c779750e05
```

Esse SHA continua sendo o baseline funcional e o merge-base obrigatório. **Não resetar a branch para esse SHA**, pois os commits seguintes contêm a própria spec/plano da Fase 13.

Antes de qualquer implementação, validar:

```bash
git fetch origin
git switch phase-13-requester-experience

git merge-base HEAD 96d88ed58df5e2d007aedd8cbed2f2c779750e05
git diff --name-only 96d88ed58df5e2d007aedd8cbed2f2c779750e05..HEAD
git status --short
```

O `merge-base` deve ser exatamente:

```text
96d88ed58df5e2d007aedd8cbed2f2c779750e05
```

Antes do primeiro commit de implementação, o diff contra esse baseline deve conter somente estes documentos de planejamento:

```text
docs/superpowers/specs/2026-09-12-phase-13-requester-experience-design.md
docs/superpowers/plans/2026-09-12-phase-13-requester-experience.md
docs/superpowers/plans/2026-09-12-phase-13-execution-handoff.md
```

Nenhum arquivo de código deve aparecer nesse diff inicial.

## Worktree

A branch já existe. Se o ambiente Codex não estiver em workspace isolado, usar `superpowers:using-git-worktrees` e criar um worktree **a partir da branch existente**, sem `-b` e sem criar outra branch.

Exemplo somente quando o fallback manual for necessário:

```bash
git worktree add .worktrees/phase-13-requester-experience phase-13-requester-experience
```

Antes disso, seguir integralmente as verificações de isolamento e `.gitignore` definidas pelo skill `using-git-worktrees`.

## Execução

Modo recomendado:

```text
superpowers:subagent-driven-development
```

Fallback:

```text
superpowers:executing-plans
```

Executar Task por Task em:

```text
RED -> GREEN -> REFACTOR -> commit
```

Antes do primeiro edit visual, usar Impeccable conforme a spec. A direção visual já foi aprovada; não reabrir rodada estética com o usuário.

## Guardrails

- não modificar `phase-12-web-demo`;
- não modificar o Draft PR #15;
- não rebasear/resetar a Fase 13 para apagar os documentos de planejamento;
- não fazer force push;
- não fazer merge;
- não marcar PR como Ready for Review;
- não excluir branch;
- não fazer push de implementação sem autorização explícita do usuário;
- preservar todos os arquivos core protegidos listados na spec/plano;
- se `jup-avatar-animated.zip` não estiver disponível, obedecer a regra de dependência da Task 7 e não fabricar substituto.

## Stop condition

Ao concluir as Tasks e gates locais, parar antes de push e reportar:

```text
branch
HEAD SHA
full pytest
frontend test/lint/build
925 historical node IDs
protected-file diff
routing / learning-prevention / web-demo smokes
Impeccable desktop review
working tree status
```
