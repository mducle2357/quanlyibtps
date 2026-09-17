import axios, { AxiosError } from 'axios';

// The access token lives only in memory (module state), never localStorage —
// only the opaque refresh token is persisted so a silent refresh can happen
// on page reload (prompt §1.4 restricts localStorage to UI prefs, not the
// business "source of truth"; a short-lived bearer token is a compromise we
// document in README rather than smuggling business data into it).
let accessToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export const REFRESH_TOKEN_KEY = 'ib_tps_refresh_token';

export const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const rt = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!rt) return null;
  try {
    const { data } = await axios.post('/api/auth/refresh', { refresh_token: rt });
    setAccessToken(data.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
    return data.access_token;
  } catch {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    return null;
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retried?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      if (!refreshPromise) refreshPromise = tryRefresh().finally(() => (refreshPromise = null));
      const newToken = await refreshPromise;
      if (newToken) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

export interface ApiErrorBody {
  error: string;
  message: string;
  current_version?: number;
}

export function apiErrorMessage(err: unknown, fallback = 'Đã có lỗi xảy ra.'): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body?.message) return body.message;
  }
  return fallback;
}

export function isConflictError(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 409;
}
