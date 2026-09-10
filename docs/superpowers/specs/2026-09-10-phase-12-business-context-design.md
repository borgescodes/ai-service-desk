# Fase 12: contexto corporativo e extensão neutra

Autorização: continuação inline na branch `phase-12-web-demo`, partindo de
`fec4ccfa156eb07056af0f6804e8e1f64986bb9a`. Sem alterações em frontend,
identidade, policy, approval, routing, lifecycle, execution ou integração CDM.

## Contrato

F12 possui o vocabulário da Juparanã. O domínio fornece os pontos neutros para
consumi-lo. LLM entende e conversa. Backend decide e executa.

Em `engine/classification.py`, definir `VocabularyResolver` como protocolo:

```python
def systems(self, text: str) -> tuple[str, ...]: ...
def canonical(self, value: str) -> str | None: ...
def aliases(self, system: str) -> tuple[str, ...]: ...
def entities(self, text: str) -> dict[str, str]: ...
```

`resolver=None` conserva todos os caminhos históricos. O argumento opcional
segue por classificação, triagem e retrieval. A implementação F12 é imutável;
não altera `SYSTEM_ALIASES` e não existe import do pacote web no domínio.
O protocolo representa somente evidência linguística; não recebe identidade,
policy, approval ou estado operacional. As entidades retornadas pela F12
contêm apenas produto explicitamente reconhecido.

A classificação usa o resolver para recuperar sistemas fundamentados e produto;
o modelo continua propondo intent segundo o contrato existente. O runtime
acrescenta contexto funcional curado à mensagem de sistema do payload, preservando
a mensagem original como dado do usuário. Reutiliza `classify_ticket` e
`OllamaClient`, sem novo cliente e sem fallback de LOCAL_AI.

A triagem usa o mesmo resolver para aliases, slots, correções e ambiguidade.
Sistema conhecido sem artigo não é sistema desconhecido. `available_systems`
continua descrevendo exclusivamente artigos reais. Retrieval continua filtrando
sistema/intenção antes da similaridade; não modifica respostas aprovadas.
Consultas de busca podem reconciliar o sistema de uma correção, como já ocorre
no legado; `problem_text` e histórico de mensagens preservam o texto original.

## Contexto F12

Catálogo declarativo em `web/business_context.py`: aliases, produtos, relações,
situação temporal, descrição funcional, versão e `BUSINESS_CONTEXT_CURRENT`.
`OFFICE 365` é a suíte; OUTLOOK, TEAMS e ONEDRIVE são produtos. CIGAM 11,
METADADOS e PORTAL RH são distintos. SAP está em implantação e coexiste com os
legados. Relações não acrescentam candidatos de sistema à mensagem.

CDM contextual exige ação de cadastro/criação, objeto material e finalidade de
revenda na mesma expressão, sem negação e sem outro sistema explícito. Compra,
pedido e movimentação isolados não bastam. Essa inferência não cria intent de
acesso, artigo aprovado, request ou execução.

CSV: somente análise offline, `HISTORICAL_LANGUAGE_ONLY`. SHA256
`26b3ca70c91db22145cf16676c0d13a8b5c847e6303ee440a0806e395b6e12bb`.
15.542 registros, todos HISTORICO_NAO_VALIDADO. Cigan: 62 registros em título ou
descrição, candidato corroborado pela taxonomia CIGAM; promoção restrita a alias
linguístico, coberta por testes. Nenhum chamado ou atendimento entra no runtime.
Não adicionar orientações a `demo_data.py`.

## Apresentação segura

Knowledge e mensagens de request continuam compostas literalmente de fatos do
backend. Em clarification, texto livre do modelo não deve poder afirmar ações
operacionais. Usar composição controlada de reconhecimento com contexto validado,
sem aceitar uma frase arbitrária como evidência. Remover a pergunta específica
de Office, pois a triagem passa a entender o alias. Manter a pergunta do domínio
fora do prompt do modelo. Mudança de segurança em ciclo e commits separados.

## Proteção e aceitação

Somente classification, triage e knowledge_retrieval têm extensão autorizada.
O workflow deve fixar os blobs exatos resultantes desses três arquivos; todos
os demais continuam comparados à baseline F11. Não usar allowlist irrestrita.
Preservar os 925 node IDs históricos e provar comportamento sem injeção.
Qwen real exige QA Windows posterior, sem confundir testes com doubles com QA.
