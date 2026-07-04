import axios from 'axios';
import { API_BASE_URL } from '../utils/constants';
import { attachParsedApiError } from './error';

const CSRF_COOKIE_NAME = 'dsa_csrf_token';
const CSRF_HEADER_NAME = 'X-DSA-CSRF';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const ADMIN_ONLY_ROUTE_PREFIXES = ['/admin', '/settings'];

const isAdminOnlyBrowserPath = (pathname: string): boolean => (
  ADMIN_ONLY_ROUTE_PREFIXES.some((routePath) => (
    pathname === routePath || pathname.startsWith(`${routePath}/`)
  ))
);

const shouldRedirectToAdminLogin = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  const pathname = window.location.pathname || '/';
  return !pathname.startsWith('/login') && isAdminOnlyBrowserPath(pathname);
};

const readCookie = (name: string): string | null => {
  if (typeof document === 'undefined') {
    return null;
  }
  const prefix = `${name}=`;
  const cookie = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  if (!cookie) {
    return null;
  }
  return decodeURIComponent(cookie.slice(prefix.length));
};

const withHeader = (headers: unknown, name: string, value: string): unknown => {
  if (headers && typeof (headers as { set?: unknown }).set === 'function') {
    (headers as { set: (key: string, val: string) => void }).set(name, value);
    return headers;
  }
  return { ...(headers as Record<string, unknown> | undefined), [name]: value };
};

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase();
  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
      config.headers = withHeader(config.headers, CSRF_HEADER_NAME, csrfToken) as typeof config.headers;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && shouldRedirectToAdminLogin()) {
      const path = window.location.pathname + window.location.search;
      const redirect = encodeURIComponent(path);
      window.location.assign(`/login?redirect=${redirect}`);
    }
    attachParsedApiError(error);
    return Promise.reject(error);
  }
);

export default apiClient;
