/**
 * Shared auth token utilities.
 * All API modules import from here instead of defining their own headers()/getToken().
 */

import { API_BASE } from './config';

const TOKEN_KEY = 'cc-token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

let _tokenPromise: Promise<string> | null = null;

export async function ensureToken(): Promise<string> {
  const existing = getToken();
  if (existing) return existing;
  if (_tokenPromise) return _tokenPromise;
  _tokenPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/token`);
      if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`);
      const data = await res.json();
      setToken(data.token);
      return data.token as string;
    } finally {
      _tokenPromise = null;
    }
  })();
  return _tokenPromise;
}

export function headers(): HeadersInit {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}
