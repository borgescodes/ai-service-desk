<div align="center">
  <img src="web/src/assets/brand/jup-avatar-main.gif" width="120" alt="Jup Resolve avatar" />

# Jup Resolve

**Uma camada inteligente de atendimento para entender, orientar e resolver solicitações de TI antes da abertura de um chamado.**

[Demo interativa](https://borgescodes.github.io/ai-service-desk/) · [Showcase](https://borgescodes.github.io/jup-resolve-showcase/)

![Version](https://img.shields.io/badge/version-0.1.0-173e25?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.14-173e25?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-173e25?style=flat-square&logo=fastapi&logoColor=white)
![Local AI](https://img.shields.io/badge/AI-Ollama-173e25?style=flat-square)

</div>

## Visão geral

Jup Resolve atua antes da abertura de um chamado tradicional.

A aplicação conversa com o solicitante, preserva o contexto da conversa, consulta conhecimento aprovado e decide qual caminho deve ser seguido: orientar o usuário, executar um fluxo autorizado ou encaminhar o caso para um técnico com o contexto já estruturado.

A arquitetura mantém uma separação clara entre interpretação e autoridade:

```text
IA entende e conversa.
Backend decide e executa.
```

O modelo auxilia na compreensão da linguagem natural. Regras de negócio, autorização, policy, routing, approval, provenance e execução permanecem sob responsabilidade da aplicação.

## Demo

A versão publicada no GitHub Pages permite experimentar os principais fluxos diretamente pelo navegador:

**Demo:** https://borgescodes.github.io/ai-service-desk/

Ela reutiliza o mesmo frontend oficial de `web/src`, mas substitui o backend por um adapter estático e determinístico com dados sintéticos.

Nenhuma integração corporativa real é executada no GitHub Pages.

Para uma visão guiada da proposta e da arquitetura:

**Showcase:** https://borgescodes.github.io/jup-resolve-showcase/

## Principais recursos

- **Atendimento conversacional:** mantém contexto ao longo da conversa.
- **Knowledge aprovada:** orientação baseada em conteúdo autorizado e versionado.
- **Playbooks:** fluxos estruturados para situações conhecidas.
- **Policy:** decisões sensíveis continuam determinísticas e controladas pelo backend.
- **Routing:** encaminhamento para o especialista responsável pelo contexto identificado.
- **Approval:** ações que exigem decisão humana permanecem sob aprovação.
- **Support handoff:** entrega o caso ao técnico com contexto e resumo estruturado.
- **Prevenção:** identifica padrões que podem virar conhecimento ou automação.
- **Local AI:** suporte a modelos executados localmente através do Ollama.
- **Demo estática:** permite experimentar o produto sem Python, backend ou modelo local.

## Arquitetura

```text
Browser
   ↓
FastAPI
   ↓
Jup Resolve Runtime
   ├── Conversation
   ├── Knowledge
   ├── Playbooks
   ├── Policy
   ├── Routing
   ├── Approval
   └── Execution
        ↓
Integrações controladas
```

No modo `LOCAL_AI`, o runtime utiliza a camada de IA configurada no projeto.

O frontend nunca acessa diretamente modelos ou integrações externas.

Isso mantém o projeto desacoplado do modelo utilizado e permite substituir a camada de IA sem transferir regras de negócio para o LLM ou SLM.

## Modos de execução

### GitHub Pages

```text
web/src
   ↓
mesmo frontend
   ↓
static_demo.mjs
   ↓
dados sintéticos
```

Não requer:

- Python
- FastAPI
- Ollama
- modelo local
- integrações externas

### Runtime determinístico

```text
DETERMINISTIC
```

Executa os fluxos de forma reproduzível e é utilizado principalmente em testes e validações.

### Local AI

```text
LOCAL_AI
```

Utiliza o runtime completo com a camada de inteligência artificial local configurada no ambiente.

## Estrutura do repositório

```text
ai-service-desk/
├── src/
│   └── ai_service_desk/      # domínio, runtime, API e integrações
├── web/
│   ├── src/                  # frontend oficial
│   ├── tests/                # testes do frontend
│   └── scripts/              # build e GitHub Pages
├── knowledge/                # conhecimento aprovado/versionado
├── playbooks/                # playbooks operacionais
├── tests/                    # testes Python
├── docs/                     # documentação técnica
├── .github/
│   └── workflows/            # CI e publicação
├── PRODUCT.md
├── DESIGN.md
└── README.md
```

## Executar localmente

### Requisitos

- Python 3.14
- Node.js 24
- Git
- Ollama para o modo `LOCAL_AI`

Crie o ambiente Python:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Prepare o frontend:

```powershell
cd web
npm ci
npm run build
cd ..
```

Inicie a aplicação:

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

## Demo estática local

Também é possível executar somente a experiência utilizada no GitHub Pages:

```powershell
cd web

npm ci
npm run build:pages

python -m http.server 8080 --directory pages-dist
```

Abra:

```text
http://127.0.0.1:8080/?static-demo=1
```

Nesse modo as chamadas utilizadas pela interface são atendidas diretamente pelo adapter estático no navegador.

## Qualidade

Frontend:

```powershell
cd web
npm run lint
npm test
npm run build
npm run build:pages
```

Backend:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Segurança e limites

Jup Resolve foi estruturado para não delegar autoridade operacional ao modelo.

- O modelo não define permissões.
- O modelo não aprova ações sensíveis.
- O modelo não recebe credenciais de integração.
- Knowledge precisa possuir provenance válida para ser tratada como orientação oficial.
- Integrações são executadas por componentes controlados da aplicação.
- A demo pública utiliza dados sintéticos e não executa ações corporativas.

## Documentação

Referências principais:

- [Contexto de produto](PRODUCT.md)
- [Sistema visual](DESIGN.md)
- [Ambiente da aplicação web](docs/environment/web-demo.md)
- [Policy e autorização](docs/policy/phase-7.md)

---

**Jup Resolve** · Entender primeiro. Agir quando necessário.
