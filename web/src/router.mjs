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

function currentLocation() {
  return globalThis.window?.location ?? globalThis.location ?? null;
}

export function appBasePath(location = currentLocation()) {
  const hostname = String(location?.hostname ?? '').toLocaleLowerCase('en-US');
  if (!hostname.endsWith('.github.io')) return '';
  const firstSegment = String(location?.pathname ?? '/').split('/').filter(Boolean)[0];
  return firstSegment ? `/${firstSegment}` : '';
}

export function stripBasePath(pathname, location = currentLocation()) {
  const base = appBasePath(location);
  const value = String(pathname || '/');
  if (!base) return value || '/';
  if (value === base) return '/';
  if (value.startsWith(`${base}/`)) return value.slice(base.length) || '/';
  return value || '/';
}

export function withBasePath(path, location = currentLocation()) {
  const value = String(path || '/');
  if (/^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith('//')) return value;
  const base = appBasePath(location);
  if (!base) return value.startsWith('/') ? value : `/${value}`;
  if (value === base || value.startsWith(`${base}/`) || value.startsWith(`${base}?`)) return value;
  if (value === '/') return `${base}/`;
  return `${base}${value.startsWith('/') ? value : `/${value}`}`;
}

export function resolveRoute(pathname) {
  const normalized = stripBasePath(pathname);
  if (/^\/solucoes\/[^/]+$/.test(normalized)) return 'solution';
  return STATIC_ROUTES.get(normalized) ?? 'solutions';
}

export function routeParams(pathname) {
  const normalized = stripBasePath(pathname);
  const match = normalized.match(/^\/solucoes\/([^/]+)$/);
  return match ? { knowledgeId: decodeURIComponent(match[1]) } : {};
}

export function routePath(route, params = {}) {
  if (route === 'solutions') return withBasePath('/');
  if (route === 'jup') return withBasePath('/jup');
  if (route === 'requests') return withBasePath('/requests');
  if (route === 'solution') return withBasePath(`/solucoes/${encodeURIComponent(params.knowledgeId)}`);
  if (route === 'prevention') return withBasePath('/demo/operacao/prevention');
  if (route === 'handoffs') return withBasePath('/demo/operacao/general');
  return withBasePath('/demo/operacao/cdm');
}

export function demoIdentityForPath(pathname) {
  const normalized = stripBasePath(pathname);
  if (normalized === '/demo/operacao/m365') return 'tecnico-m365';
  if (normalized === '/demo/operacao/general') return 'tecnico-geral';
  if (normalized === '/demo/operacao/prevention') return 'tecnico-geral';
  if (normalized === '/demo/operacao/cdm' || normalized === '/operations') return 'tecnico-cdm';
  if (normalized === '/operations/prevention') return 'tecnico-geral';
  return 'pedro-miranda';
}
