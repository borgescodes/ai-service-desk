# Jup Resolve

> Entender primeiro. Agir quando necessário.

O Jup Resolve é uma camada inteligente de atendimento para Service Desk. A aplicação conversa com o solicitante, preserva contexto, consulta conhecimento aprovado, encaminha quando necessário e mantém decisões sensíveis sob controle do backend.

A proposta é reduzir chamados evitáveis sem transformar toda necessidade em automação. Quando existe orientação segura e aprovada, o Jup pode orientar. Quando existe um fluxo autorizado, pode conduzir. Quando a situação exige avaliação humana, encaminha o contexto já organizado.

## Teste a aplicação

O projeto possui duas formas de executar a mesma experiência de frontend.

### GitHub Pages

A publicação no GitHub Pages reutiliza fielmente o frontend oficial de `web/src`.

Não existe uma segunda interface, uma reconstrução visual ou uma versão inspirada no produto. Os mesmos componentes, estilos, tokens, assets, animações e estados de interface são usados no runtime local e no Pages.

No Pages, somente a camada de transporte muda:

```text
web/src
  ↓
mesmo frontend
  ↓
adapter estático e determinístico
  ↓
dados sintéticos no navegador
```

Esse modo não depende de Python, FastAPI, Ollama ou Qwen. Nenhuma ação corporativa é executada.

A demonstração estática permite testar:

- Central de Suporte e busca de artigos;
- conversa com o Jup;
- orientação de Microsoft 365;
- solicitação simulada de acesso ao CDM;
- Minhas solicitações;
- troca entre solicitante e perfis técnicos;
- aprovação e rejeição simuladas;
- encaminhamentos;
- oportunidades de prevenção.

As respostas da demo estática são determinísticas. Elas servem para exercitar a experiência e os estados do produto, não para representar inferência de um modelo.

### Runtime completo local

O runtime completo continua no repositório e não foi removido ou substituído pela demo estática.

```text
Browser
  ↓
FastAPI
  ↓
DemoRuntime / conversational core
  ├── interpretação
  ├── knowledge aprovada
  ├── playbooks
  ├── policy
  ├── routing
  ├── approval
  └── execution
       ↓
integrações controladas
```

No modo `LOCAL_AI`, o runtime pode usar Ollama e os modelos locais configurados pelo projeto. O navegador nunca conversa diretamente com o modelo ou com integrações externas.

## Princípio de arquitetura

```text
IA entende e conversa.
Backend decide e executa.
```

O modelo pode auxiliar interpretação e linguagem natural. Policy, autorização, routing, approval, provenance, execução e identidade permanecem regras da aplicação.

Essa separação permite trocar o modelo sem transferir regras de negócio e segurança para o LLM ou SLM.

## Estrutura do repositório

```text
ai-service-desk/
├── src/ai_service_desk/   # domínio, runtime, API e integrações
├── web/
│   ├── src/               # frontend oficial
│   ├── tests/             # testes do frontend
│   └── scripts/           # builds local e GitHub Pages
├── knowledge/             # conhecimento versionado permitido
├── playbooks/             # playbooks versionados
├── tests/                 # testes Python
├── docs/                  # documentação técnica
└── .github/workflows/     # CI e publicação
```

## Frontend

A fonte de verdade visual é `web/src`.

O build do Pages parte do mesmo build normal e apenas:

1. adapta caminhos absolutos para o subdiretório do GitHub Pages;
2. adiciona o fallback de SPA em `404.html`;
3. ativa o adapter estático quando a aplicação roda em `github.io`.

CSS, layout, componentes e animações não possuem uma implementação paralela para a demo pública.

### Testar a versão estática localmente

Requer Node 24.

```powershell
cd web
npm ci
npm run lint
npm test
npm run build:pages
python -m http.server 8080 --directory pages-dist
```

Abra:

```text
http://127.0.0.1:8080/?static-demo=1
```

Nesse modo, as chamadas de API são atendidas no navegador.

## Executar o runtime completo

Requisitos principais:

- Python 3.14;
- Git;
- Node 24;
- Ollama somente para `LOCAL_AI`.

Crie o ambiente:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Instale e valide o frontend:

```powershell
cd web
npm ci
npm run lint
npm test
npm run build
cd ..
```

No Windows:

```powershell
.\run-web-demo.cmd
```

Ou:

```powershell
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
```

Abra:

```text
http://127.0.0.1:8000/
```

## Modos do runtime

- `DETERMINISTIC`: comportamento reproduzível para validação e testes.
- `LOCAL_AI`: usa a camada local de IA configurada no projeto.

O modo do GitHub Pages é separado desses dois. Ele simula o contrato da API somente para permitir testar a interface sem infraestrutura local.

## Qualidade

Backend:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Frontend:

```powershell
cd web
npm run lint
npm test
npm run build
```

Build do Pages:

```powershell
cd web
npm run build:pages
```

O workflow do GitHub Pages executa lint, testes e build antes da publicação.

## GitHub Pages

O workflow `.github/workflows/pages.yml` publica somente `web/pages-dist`.

O artefato publicado contém o frontend e os dados sintéticos necessários à demo estática. Backend Python, modelos locais, índices e integrações não são executados no GitHub Pages.

Após o workflow estar na `main`:

```text
Settings
→ Pages
→ Source
→ GitHub Actions
```

Endereço esperado:

```text
https://borgescodes.github.io/ai-service-desk/
```

## Segurança e limites

- O browser não recebe credenciais de integração.
- O Pages não executa ações corporativas.
- Os dados da demo estática são sintéticos.
- Knowledge oficial continua dependente de provenance aprovada no runtime completo.
- Histórico recuperado não se torna automaticamente procedimento aprovado.
- A demo estática não substitui testes de policy, autorização ou integrações reais.

## CLI

```powershell
python -m ai_service_desk --help
```

A documentação técnica detalhada está em `docs/`.
