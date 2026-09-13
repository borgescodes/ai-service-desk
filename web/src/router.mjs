const ROUTES = new Map([
  ['/', 'jup'],
  ['/jup', 'jup'],
  ['/requests', 'requests'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
]);

export function resolveRoute(pathname) {
  return ROUTES.get(pathname) ?? 'jup';
}

export function routePath(route) {
  for (const [path, name] of ROUTES) {
    if (name === route && path !== '/') return path;
  }
  return '/jup';
}
