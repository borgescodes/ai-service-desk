const M365_URL = 'https://mysignins.microsoft.com/security-info/password/change';
const CDM_URL = 'https://cdm.juparana.com.br/';

const CATEGORY_LABELS = Object.freeze({
  'acessos-rotinas': 'Acessos e rotinas',
  'erros-sistemas': 'Erros em sistemas',
  'impressao-office-aplicativos': 'Impressão, Office e aplicativos',
  'rede-internet': 'Rede e internet',
});

const ARTICLES = Object.freeze([
  {
    knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001',
    title: 'Como solicitar acesso ao CDM',
    category: CATEGORY_LABELS['acessos-rotinas'],
    category_key: 'acessos-rotinas',
    system: 'CDM',
    answer: `Para solicitar seu acesso ao CDM:\n\n1. Acesse ${CDM_URL}.\n2. Na tela de entrada, clique em Solicitar Acesso.\n3. Informe seu e-mail corporativo @juparana.com.br.\n4. Selecione uma ou mais áreas de negócio relacionadas à sua atuação.\n5. Clique em Enviar.\n6. Sua solicitação será registrada e encaminhada para análise da governança do CDM.\n7. Depois que o acesso for aprovado e provisionado, você receberá um e-mail informando que o acesso ao CDM foi liberado.\n8. No e-mail, utilize a opção Entrar no CDM ou acesse novamente o endereço do CDM.\n9. Entre utilizando sua conta corporativa Microsoft 365.\n\nSe aparecer um erro ou você não conseguir entrar após a liberação, informe a mensagem ao suporte. Não envie sua senha.`,
    procedure_url: CDM_URL,
    provenance: { status: 'APPROVED', source: 'SYNTHETIC_DEMO' },
  },
  {
    knowledge_id: 'KB-SYN-M365-PASSWORD-001',
    title: 'Redefinir sua senha do Microsoft 365',
    category: CATEGORY_LABELS['impressao-office-aplicativos'],
    category_key: 'impressao-office-aplicativos',
    system: 'OFFICE 365',
    answer: 'Vamos redefinir sua senha do Microsoft 365.\n\n1. Acesse a página de redefinição de senha da Microsoft.\n2. Informe seu e-mail corporativo e conclua a verificação exibida na tela.\n3. Clique em Avançar.\n4. Escolha um dos métodos de confirmação disponíveis para sua conta.\n5. Confirme sua identidade.\n6. Crie uma nova senha seguindo os requisitos apresentados.\n7. Tente entrar novamente no Outlook, Teams e demais aplicativos do Microsoft 365.\n\nFaça esse procedimento e me diga se conseguiu acessar.',
    procedure_url: M365_URL,
    provenance: { status: 'APPROVED', source: 'SYNTHETIC_DEMO' },
  },
]);

const CATALOG = Object.freeze([
  ...ARTICLES,
  { knowledge_id: 'CAT-APP-START', title: 'Sistema não abre ou fecha sozinho', category: CATEGORY_LABELS['erros-sistemas'], category_key: 'erros-sistemas', system: 'APLICATIVOS' },
  { knowledge_id: 'CAT-CIGAM-START', title: 'O CIGAM apresenta erro ao iniciar', category: CATEGORY_LABELS['erros-sistemas'], category_key: 'erros-sistemas', system: 'CIGAM' },
  { knowledge_id: 'CAT-WEB-BLANK', title: 'Sistema web fica em tela branca', category: CATEGORY_LABELS['erros-sistemas'], category_key: 'erros-sistemas', system: 'SISTEMA WEB' },
  { knowledge_id: 'CAT-PRINTER-OFFLINE', title: 'Impressora aparece offline', category: CATEGORY_LABELS['impressao-office-aplicativos'], category_key: 'impressao-office-aplicativos', system: 'IMPRESSORA' },
  { knowledge_id: 'CAT-OUTLOOK-SYNC', title: 'Outlook não envia ou recebe mensagens', category: CATEGORY_LABELS['impressao-office-aplicativos'], category_key: 'impressao-office-aplicativos', system: 'OUTLOOK' },
  { knowledge_id: 'CAT-TEAMS-AUDIO', title: 'Teams está sem áudio ou microfone', category: CATEGORY_LABELS['impressao-office-aplicativos'], category_key: 'impressao-office-aplicativos', system: 'TEAMS' },
  { knowledge_id: 'CAT-OFFICE-AUTH', title: 'Aplicativo do Office pede autenticação repetidamente', category: CATEGORY_LABELS['impressao-office-aplicativos'], category_key: 'impressao-office-aplicativos', system: 'OFFICE 365' },
  { knowledge_id: 'CAT-WIFI', title: 'Estou conectado ao Wi-Fi, mas sem internet', category: CATEGORY_LABELS['rede-internet'], category_key: 'rede-internet', system: 'REDE' },
  { knowledge_id: 'CAT-CABLE', title: 'Computador conectado por cabo está sem rede', category: CATEGORY_LABELS['rede-internet'], category_key: 'rede-internet', system: 'REDE' },
  { knowledge_id: 'CAT-ONE-SITE', title: 'Apenas um site ou sistema não abre', category: CATEGORY_LABELS['rede-internet'], category_key: 'rede-internet', system: 'REDE' },
]);

const BASE_IDENTITIES = Object.freeze([
  {
    identity_id: 'pedro-miranda',
    name: 'Fulano de Tal',
    email: 'fulano.tal@example.invalid',
    job_title: 'Colaborador',
    area: 'Revenda - Matriz',
    role: 'REQUESTER',
    can_operate: false,
  },
  { identity_id: 'tecnico-cdm', name: 'Técnico CDM', area: 'TI', role: 'TECHNICIAN', can_operate: true },
  { identity_id: 'tecnico-m365', name: 'Técnico Microsoft 365', area: 'TI', role: 'TECHNICIAN', can_operate: true },
  { identity_id: 'tecnico-geral', name: 'Técnico Geral', area: 'TI', role: 'TECHNICIAN', can_operate: true },
]);

const PREVENTION = Object.freeze([
  {
    opportunity_id: 'OPP-DEMO-001',
    category: 'KNOWLEDGE_CANDIDATE',
    category_label: 'Candidato a conhecimento',
    occurrence_count: 18,
    system: 'OFFICE 365',
    intent: 'PROBLEMA_ACESSO',
    capability: '',
    area: 'Comercial',
    reason_codes: ['REPEATED_PATTERN'],
    explanation: 'O histórico sintético da demo apresenta recorrência suficiente para sugerir uma orientação preventiva sobre acesso ao Microsoft 365.',
    explanation_code: 'STATIC_DEMO_KNOWLEDGE_CANDIDATE',
  },
  {
    opportunity_id: 'OPP-DEMO-002',
    category: 'AUTOMATION_CANDIDATE',
    category_label: 'Candidato a automação',
    occurrence_count: 11,
    system: 'CDM',
    intent: 'CDM_ACCESS_REQUEST',
    capability: 'CDM_ACCESS_REQUEST',
    area: 'Revenda',
    reason_codes: ['REPEATED_PATTERN', 'CONTROLLED_FLOW'],
    explanation: 'O histórico sintético da demo identifica um fluxo recorrente de solicitação de acesso ao CDM com etapas controladas.',
    explanation_code: 'STATIC_DEMO_AUTOMATION_CANDIDATE',
  },
]);

export class StaticDemoError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = 'StaticDemoError';
    this.status = status;
    this.code = code;
  }
}

const clone = value => value === undefined ? undefined : structuredClone(value);
const nowIso = () => new Date().toISOString();

const state = {
  identities: clone(BASE_IDENTITIES),
  requests: new Map(),
  handoffs: new Map(),
  identitySequence: 1,
  requestSequence: 1,
  handoffSequence: 1,
};

function requester(identityId) {
  const identity = state.identities.find(item => item.identity_id === identityId);
  if (!identity || identity.role !== 'REQUESTER') {
    throw new StaticDemoError(403, 'NOT_AUTHORIZED', 'Esta identidade não possui perfil de solicitante.');
  }
  return identity;
}

function technician(identityId) {
  const identity = state.identities.find(item => item.identity_id === identityId);
  if (!identity || identity.role !== 'TECHNICIAN') {
    throw new StaticDemoError(403, 'NOT_AUTHORIZED', 'Esta identidade não possui perfil técnico.');
  }
  return identity;
}

function publicRequest(record) {
  const { _identity_id, ...payload } = record;
  return clone(payload);
}

function confidence() {
  return {
    level: 'HIGH',
    label: 'Alta',
    percent: 96,
    explanations: [
      { kind: 'positive', text: 'Sistema e intenção identificados no pedido.' },
      { kind: 'positive', text: 'Fluxo sintético possui regra de encaminhamento conhecida.' },
    ],
  };
}

function createCdmRequest(identityId) {
  const identity = requester(identityId);
  const existing = [...state.requests.values()].find(item =>
    item._identity_id === identityId && item.system === 'CDM' && item.state === 'PENDING_APPROVAL'
  );
  if (existing) return existing;

  const requestId = `REQ-DEMO-${String(state.requestSequence++).padStart(3, '0')}`;
  const created = nowIso();
  const record = {
    _identity_id: identityId,
    request_id: requestId,
    version: 2,
    state: 'PENDING_APPROVAL',
    state_label: 'Aguardando aprovação',
    requester: {
      name: identity.name,
      username: identity.email?.split('@')[0] || identity.identity_id,
      email: identity.email || '',
      area: identity.area || '',
      job_title: identity.job_title || '',
      identity_source: 'STATIC_DEMO_SESSION',
    },
    system: 'CDM',
    intent: 'CDM_ACCESS_REQUEST',
    requested_role: 'SOLICITANTE',
    business_scope: 'REVENDAS',
    scope_source: 'USER_MESSAGE',
    scope_mismatch: false,
    scope_confirmed: true,
    purpose: 'Solicitar materiais para uma revenda',
    capability: 'CDM_ACCESS_REQUEST',
    knowledge_id: null,
    playbook_id: 'PB-SYN-CDM-ACCESS-001',
    playbook_version: '1',
    confidence: confidence(),
    policy: {
      decision: 'REQUIRE_APPROVAL',
      requires_approval: true,
      policy_id: 'POLICY-CDM-ACCESS',
      reason_code: 'HUMAN_APPROVAL_REQUIRED',
      reason: 'A solicitação exige aprovação humana antes da execução.',
    },
    routing: {
      technician_id: 'TECH-CDM',
      technician_name: 'Técnico CDM',
      system: 'CDM',
      capability: 'CDM_ACCESS_REQUEST',
    },
    timeline: [
      { label: 'Solicitação registrada', occurred_at: created },
      { label: 'Encaminhada para aprovação', occurred_at: created },
    ],
    created_at: created,
    updated_at: created,
    decided_by: null,
    decided_at: null,
    execution_started_at: null,
    execution_finished_at: null,
    execution_result_code: null,
    execution_error_code: null,
  };
  state.requests.set(requestId, record);
  return record;
}

function createHandoff(identityId, message, system = 'GENERAL_IT') {
  const identity = requester(identityId);
  const technicianIdentity = system === 'OFFICE 365'
    ? state.identities.find(item => item.identity_id === 'tecnico-m365')
    : state.identities.find(item => item.identity_id === 'tecnico-geral');
  const existing = [...state.handoffs.values()].find(item =>
    item.requester.identity_id === identityId && item.system === system
  );
  if (existing) return existing;

  const handoffId = `HANDOFF-DEMO-${String(state.handoffSequence++).padStart(3, '0')}`;
  const handoff = {
    handoff_id: handoffId,
    system,
    capability: system === 'OFFICE 365' ? 'MICROSOFT_365_SUPPORT_REQUEST' : 'GENERAL_IT_SUPPORT',
    technician: {
      technician_id: technicianIdentity.identity_id === 'tecnico-m365' ? 'TECH-M365' : 'TECH-GENERAL',
      username: technicianIdentity.identity_id,
      name: technicianIdentity.name,
      email: '',
    },
    requester: {
      identity_id: identityId,
      username: identity.email?.split('@')[0] || identity.identity_id,
      name: identity.name,
      email: identity.email || '',
      area: identity.area || '',
      identity_source: 'STATIC_DEMO_SESSION',
    },
    technical_summary: `Atendimento simulado encaminhado após triagem: ${message}`,
    source_conversation: [
      { role: 'USER', text: message },
      { role: 'JUP', text: 'Vou encaminhar o contexto para o especialista responsável.' },
    ],
    confidence: { level: 'MEDIUM', label: 'Média', percent: 74 },
  };
  state.handoffs.set(handoffId, handoff);
  return handoff;
}

function requestSummary(identityId) {
  const items = [...state.requests.values()]
    .filter(item => item._identity_id === identityId)
    .map(item => ({
      request_id: item.request_id,
      system: item.system,
      state_label: item.state_label,
    }));
  const count = items.length;
  return {
    status: 'REQUESTS_LISTED',
    request_id: null,
    request_summary: { count, items: clone(items) },
    presentation: { cta: count ? 'REQUESTS' : null },
    assistant_message: count
      ? `Você tem ${count} ${count === 1 ? 'solicitação' : 'solicitações'} para acompanhar.\n\n${items.map(item => `${item.system} · ${item.state_label} (${item.request_id})`).join('\n')}`
      : 'Você ainda não tem solicitações para acompanhar.',
  };
}

function articleResult(article, message) {
  return {
    status: 'KNOWLEDGE_FOUND',
    request_id: null,
    knowledge_id: article.knowledge_id,
    article: {
      knowledge_id: article.knowledge_id,
      title: article.title,
      category: article.category,
      system: article.system,
      provenance: article.provenance,
    },
    procedure_url: article.procedure_url,
    assistant_message: article.answer,
    echoed_message: message,
  };
}

function jupMessage(identityId, message) {
  requester(identityId);
  const clean = String(message || '').trim();
  const normalized = clean.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

  if (clean === '/solicitacoes' || /(?:minhas? solicitacoes|meu pedido|pedido pendente)/i.test(normalized)) {
    return requestSummary(identityId);
  }
  if (/^(oi|ola|bom dia|boa tarde|boa noite)\b/.test(normalized)) {
    const firstName = requester(identityId).name.split(' ')[0];
    return { status: 'SOCIAL', request_id: null, assistant_message: `Olá, ${firstName}! Como posso ajudar?` };
  }
  if (normalized.includes('cdm') && /(acesso|acessar|liberar|permissao|solicitar)/.test(normalized)) {
    const record = createCdmRequest(identityId);
    return {
      status: 'PENDING_APPROVAL',
      request_id: record.request_id,
      state: record.state,
      assistant_message: `Entendi. Registrei a solicitação ${record.request_id} para acesso ao CDM e encaminhei para aprovação. Você pode acompanhar o andamento em Minhas solicitações.`,
    };
  }
  if (/(microsoft 365|office|outlook|senha|nao consigo entrar)/.test(normalized)) {
    return articleResult(ARTICLES.find(item => item.knowledge_id === 'KB-SYN-M365-PASSWORD-001'), clean);
  }
  if (/impressora/.test(normalized)) {
    return { status: 'KNOWLEDGE_FOUND', request_id: null, assistant_message: 'Confirme se a impressora está ligada, verifique papel e avisos no painel, selecione a impressora correta e tente uma página de teste. Se continuar offline, informe ao suporte o nome da impressora, o local e a mensagem exibida.' };
  }
  if (/(wi-?fi|internet|rede)/.test(normalized)) {
    return { status: 'KNOWLEDGE_FOUND', request_id: null, assistant_message: 'Teste outro site conhecido e confira se outros dispositivos na mesma rede também apresentam falha. Se persistir, informe ao suporte o local, a rede utilizada e o horário. Não altere IP ou DNS manualmente.' };
  }
  if (/(cigam|erro|tela branca|travando|nao abre)/.test(normalized)) {
    const handoff = createHandoff(identityId, clean, 'GENERAL_IT');
    return {
      status: 'SUPPORT_HANDOFF_PENDING',
      request_id: null,
      support_handoff: clone(handoff),
      assistant_message: 'Entendi o problema. Como não há uma ação automática segura para esse caso na demo estática, encaminhei o contexto para o Técnico Geral.',
    };
  }
  if (/(bolo|receita|futebol|filme)/.test(normalized)) {
    return { status: 'OUT_OF_SCOPE', request_id: null, assistant_message: 'Posso ajudar com dúvidas, acessos e problemas relacionados ao suporte de TI. Se quiser, descreva o sistema ou equipamento com que precisa de ajuda.' };
  }
  return { status: 'NEEDS_CLARIFICATION', request_id: null, assistant_message: 'Entendi. Qual sistema, aplicativo ou equipamento está envolvido, e o que aparece na tela?' };
}

function searchFaq(url) {
  const query = (url.searchParams.get('q') || '').trim();
  const category = (url.searchParams.get('category') || '').trim();
  const normalized = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  const q = normalized(query);
  const items = CATALOG.filter(item => {
    if (category && item.category_key !== category) return false;
    if (!q) return true;
    return normalized([item.title, item.system, item.category].join(' ')).includes(q);
  }).slice(0, 16).map(item => ({
    knowledge_id: item.knowledge_id,
    title: item.title,
    category: item.category,
    system: item.system,
  }));
  return { items, total: items.length };
}

function faqGroups() {
  const summaries = ARTICLES.map(item => ({
    knowledge_id: item.knowledge_id,
    title: item.title,
    category: item.category,
    system: item.system,
  }));
  return {
    groups: Object.entries(CATEGORY_LABELS).map(([key, label]) => ({
      key,
      label,
      items: summaries.filter(item => ARTICLES.find(article => article.knowledge_id === item.knowledge_id)?.category_key === key),
    })),
    total: summaries.length,
  };
}

function updateRequest(requestId, action, identityId, expectedVersion) {
  technician(identityId);
  const record = state.requests.get(requestId);
  if (!record) throw new StaticDemoError(404, 'REQUEST_NOT_FOUND', 'Solicitação não encontrada.');
  if (identityId !== 'tecnico-cdm') throw new StaticDemoError(403, 'NOT_AUTHORIZED', 'Esta identidade não pode decidir esta solicitação.');
  if (record.state !== 'PENDING_APPROVAL') throw new StaticDemoError(409, 'INVALID_STATE_TRANSITION', 'A solicitação não aceita esta operação no estado atual.');
  if (Number(expectedVersion) !== Number(record.version)) throw new StaticDemoError(409, 'VERSION_CONFLICT', 'A solicitação foi alterada. Recarregue e tente novamente.');

  const timestamp = nowIso();
  if (action === 'reject') {
    record.state = 'REJECTED';
    record.state_label = 'Rejeitada';
    record.version += 1;
    record.decided_by = 'TECH-CDM';
    record.decided_at = timestamp;
    record.updated_at = timestamp;
    record.timeline.push({ label: 'Solicitação rejeitada', occurred_at: timestamp });
    return publicRequest(record);
  }

  record.state = 'COMPLETED';
  record.state_label = 'Concluída';
  record.version += 2;
  record.decided_by = 'TECH-CDM';
  record.decided_at = timestamp;
  record.execution_started_at = timestamp;
  record.execution_finished_at = timestamp;
  record.execution_result_code = 'SUCCESS';
  record.updated_at = timestamp;
  record.timeline.push(
    { label: 'Solicitação aprovada', occurred_at: timestamp },
    { label: 'Execução simulada concluída', occurred_at: timestamp },
  );
  return publicRequest(record);
}

function detectsStaticDemo(location) {
  const hostname = String(location?.hostname ?? '').toLocaleLowerCase('en-US');
  if (hostname.endsWith('.github.io')) return true;
  const params = new URLSearchParams(String(location?.search ?? ''));
  return params.get('static-demo') === '1';
}

let staticDemoSession = detectsStaticDemo(
  globalThis.window?.location ?? globalThis.location ?? null,
);

export function isStaticDemo(location) {
  if (location !== undefined) return detectsStaticDemo(location);
  if (staticDemoSession) return true;
  staticDemoSession = detectsStaticDemo(
    globalThis.window?.location ?? globalThis.location ?? null,
  );
  return staticDemoSession;
}

export async function staticApiRequest(path, { method = 'GET', body, identityId, signal } = {}) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  const url = new URL(path, 'https:' + '//static-demo.invalid');
  const verb = String(method || 'GET').toUpperCase();

  if (url.pathname === '/api/session/identities' && verb === 'GET') return clone(state.identities);
  if (url.pathname === '/api/session/identities' && verb === 'POST') {
    const name = String(body?.name || '').trim();
    const email = String(body?.email || '').trim();
    const jobTitle = String(body?.job_title || '').trim();
    const area = String(body?.area || '').trim();
    if (!name || !email || !jobTitle || !area) throw new StaticDemoError(422, 'INVALID_DEMO_IDENTITY', 'Preencha nome, cargo e área para criar o usuário da demonstração.');
    const identity = {
      identity_id: `demo-requester-${state.identitySequence++}`,
      name, email, job_title: jobTitle, area, role: 'REQUESTER', can_operate: false,
    };
    state.identities.push(identity);
    return clone(identity);
  }

  if (url.pathname === '/api/faq' && verb === 'GET') return faqGroups();
  if (url.pathname === '/api/faq/search' && verb === 'GET') return searchFaq(url);

  const faqMatch = url.pathname.match(/^\/api\/faq\/([^/]+)$/);
  if (faqMatch && verb === 'GET') {
    const id = decodeURIComponent(faqMatch[1]);
    const article = ARTICLES.find(item => item.knowledge_id === id);
    if (!article) throw new StaticDemoError(404, 'FAQ_NOT_FOUND', 'Solução não encontrada.');
    return clone(article);
  }

  if (url.pathname === '/api/jup/messages' && verb === 'POST') return clone(jupMessage(identityId, body?.message));
  if (url.pathname === '/api/jup/conversation/reset' && verb === 'POST') {
    requester(identityId);
    return { status: 'RESET' };
  }

  if (url.pathname === '/api/requests' && verb === 'GET') {
    requester(identityId);
    return [...state.requests.values()].filter(item => item._identity_id === identityId).map(publicRequest);
  }

  const requestDetail = url.pathname.match(/^\/api\/requests\/([^/]+)$/);
  if (requestDetail && verb === 'GET') {
    requester(identityId);
    const record = state.requests.get(decodeURIComponent(requestDetail[1]));
    if (!record) throw new StaticDemoError(404, 'REQUEST_NOT_FOUND', 'Solicitação não encontrada.');
    if (record._identity_id !== identityId) throw new StaticDemoError(403, 'NOT_AUTHORIZED', 'Solicitação não pertence ao solicitante atual.');
    return publicRequest(record);
  }

  const decision = url.pathname.match(/^\/api\/requests\/([^/]+)\/(approve|reject)$/);
  if (decision && verb === 'POST') return updateRequest(decodeURIComponent(decision[1]), decision[2], identityId, body?.expected_version);

  if (url.pathname === '/api/operations/approvals' && verb === 'GET') {
    technician(identityId);
    if (identityId !== 'tecnico-cdm') return [];
    return [...state.requests.values()].filter(item => item.state === 'PENDING_APPROVAL').map(publicRequest);
  }

  const approvalDetail = url.pathname.match(/^\/api\/operations\/approvals\/([^/]+)$/);
  if (approvalDetail && verb === 'GET') {
    technician(identityId);
    const record = state.requests.get(decodeURIComponent(approvalDetail[1]));
    if (!record || identityId !== 'tecnico-cdm') throw new StaticDemoError(404, 'REQUEST_NOT_FOUND', 'Solicitação não encontrada.');
    return publicRequest(record);
  }

  if (url.pathname === '/api/operations/handoffs' && verb === 'GET') {
    technician(identityId);
    return [...state.handoffs.values()].filter(item => {
      if (identityId === 'tecnico-m365') return item.technician.technician_id === 'TECH-M365';
      if (identityId === 'tecnico-geral') return item.technician.technician_id === 'TECH-GENERAL';
      return false;
    }).map(clone);
  }

  if (url.pathname === '/api/operations/prevention' && verb === 'GET') {
    technician(identityId);
    return clone(PREVENTION);
  }

  const preventionDetail = url.pathname.match(/^\/api\/operations\/prevention\/([^/]+)$/);
  if (preventionDetail && verb === 'GET') {
    technician(identityId);
    const item = PREVENTION.find(entry => entry.opportunity_id === decodeURIComponent(preventionDetail[1]));
    if (!item) throw new StaticDemoError(404, 'PREVENTION_NOT_FOUND', 'Oportunidade de prevenção não encontrada.');
    return clone(item);
  }

  throw new StaticDemoError(404, 'STATIC_DEMO_ROUTE_NOT_FOUND', 'Esta operação não está disponível na demonstração estática.');
}
