const TOKEN_KEY = 'sporthub_access_token';
const REFRESH_TOKEN_KEY = 'sporthub_refresh_token';
export const readToken = () => localStorage.getItem(TOKEN_KEY);
export const saveToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const readRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY);
export const saveRefreshToken = (token: string) => localStorage.setItem(REFRESH_TOKEN_KEY, token);
export const clearToken = () => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_TOKEN_KEY); };
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refreshToken = readRefreshToken(); if (!refreshToken) return false;
  if (!refreshPromise) refreshPromise = fetch('/api/auth/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshToken }) }).then(async (response) => {
    if (!response.ok) return false;
    const result = await response.json() as { access_token: string; refresh_token: string };
    saveToken(result.access_token); saveRefreshToken(result.refresh_token); return true;
  }).catch(() => false).finally(() => { refreshPromise = null; });
  return refreshPromise;
}

/**
 * Tracks whether a session-expired event has already been dispatched for this
 * browser session so we never fire it more than once (e.g. when multiple
 * in-flight requests all return 401 at the same time).
 */
let sessionExpiredDispatched = false;
window.addEventListener('sporthub-session-expired', () => {
  // Reset the flag after a tick so future logins can expire again.
  setTimeout(() => { sessionExpiredDispatched = false; }, 0);
});

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const token = readToken();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15_000);
  const abort = () => controller.abort();
  init.signal?.addEventListener('abort', abort, { once: true });
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init, signal: controller.signal,
      headers: {
        ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Yêu cầu quá thời gian chờ. Vui lòng thử lại.');
    throw new Error('Không thể kết nối SportHub. Vui lòng kiểm tra mạng hoặc thử lại sau.');
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener('abort', abort);
  }

  if (!response.ok) {
    if (response.status === 401) {
      if (!retried && path !== '/auth/refresh' && await tryRefresh()) return apiRequest<T>(path, init, true);
      clearToken();
      localStorage.removeItem('sporthub_auth');
      // Only dispatch the event if we HAD a token (i.e. this is an actual
      // expiry, not the initial unauthenticated probe of /auth/me).
      if (token && !sessionExpiredDispatched) {
        sessionExpiredDispatched = true;
        window.dispatchEvent(new Event('sporthub-session-expired'));
      }
    }
    const payload = await response.json().catch(() => null) as { detail?: string | Array<{ msg?: string }> } | null;
    const detail = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join('. ')
      : payload?.detail;
    const fallback: Record<number, string> = {
      401: 'Phiên đăng nhập không hợp lệ hoặc đã hết hạn.', 403: 'Bạn không có quyền thực hiện thao tác này.',
      404: 'Không tìm thấy dữ liệu yêu cầu.', 409: 'Dữ liệu đã thay đổi hoặc bị trùng. Vui lòng tải lại.',
      422: 'Dữ liệu gửi lên chưa hợp lệ.', 500: 'Máy chủ gặp lỗi. Vui lòng thử lại sau.',
    };
    throw new ApiError(detail || fallback[response.status] || `Yêu cầu thất bại (${response.status}).`, response.status);
  }

  return response.status === 204 ? undefined as T : (response.json() as Promise<T>);
}

export async function apiBlob(path: string): Promise<Blob> {
  const token = readToken();
  const response = await fetch(`/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(payload?.detail || 'Không tải được tệp riêng tư.', response.status);
  }
  return response.blob();
}
