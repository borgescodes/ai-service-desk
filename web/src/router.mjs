const STATIC_ROUTES = new Map([
  ['/', 'solutions'],
  ['/jup', 'jup'],
  ['/requests', 'requests'],
  ['/demo/operacao/cdm', 'approvals'],
  ['/demo/operacao/m365', 'approvals'],
  ['/demo/operacao/general', 'handoffs'],
  ['/demo/operacao/prevention', 'prevention'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
]);

export function resolveRoute(pathname) {
  if (/^\/solucoes\/[^/]+$/.test(pathname)) return 'solution';
  return STATIC_ROUTES.get(pathname) ?? 'solutions';
}

export function routeParams(pathname) {
  const match = pathname.match(/^\/solucoes\/([^/]+)$/);
  return match ? { knowledgeId: decodeURIComponent(match[1]) } : {};
}

export function routePath(route, params = {}) {
  if (route === 'solutions') return '/';
  if (route === 'jup') return '/jup';
  if (route === 'requests') return '/requests';
  if (route === 'solution') return `/solucoes/${encodeURIComponent(params.knowledgeId)}`;
  if (route === 'prevention') return '/demo/operacao/prevention';
  if (route === 'handoffs') return '/demo/operacao/general';
  return '/demo/operacao/cdm';
}

export function demoIdentityForPath(pathname) {
  if (pathname === '/demo/operacao/m365') return 'tecnico-m365';
  if (pathname === '/demo/operacao/general') return 'tecnico-geral';
  if (pathname === '/demo/operacao/prevention') return 'tecnico-geral';
  if (pathname === '/demo/operacao/cdm' || pathname === '/operations') return 'tecnico-cdm';
  if (pathname === '/operations/prevention') return 'tecnico-geral';
  return 'pedro-miranda';
}
