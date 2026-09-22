import { isStaticDemo, staticApiRequest, StaticDemoError } from './static_demo.mjs';

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export async function apiRequest(path, { method = 'GET', body, identityId, signal } = {}) {
  if (isStaticDemo()) {
    try {
      return await staticApiRequest(path, { method, body, identityId, signal });
    } catch (error) {
      if (error instanceof StaticDemoError) {
        throw new ApiError(error.status, error.code, error.message);
      }
      throw error;
    }
  }

  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (identityId) headers['X-Demo-Identity'] = identityId;

  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload?.error ?? {};
    throw new ApiError(
      response.status,
      error.code ?? 'HTTP_ERROR',
      error.message ?? 'Não foi possível concluir a operação.',
    );
  }
  return payload;
}
