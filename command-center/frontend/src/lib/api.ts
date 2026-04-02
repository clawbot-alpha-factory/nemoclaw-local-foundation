/**
 * Command Center API client.
 * Talks to the FastAPI backend at /api/*.
 */

import type { SystemState } from './types';

const API_BASE = '/api';

function getToken(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('cc-token') || '';
}

export function setToken(token: string): void {
  localStorage.setItem('cc-token', token);
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('UNAUTHORIZED');
    }
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json();
}

export const api = {
  getState: () => apiFetch<SystemState>('/state'),
  getSkills: () => apiFetch<SystemState['skills']>('/state/skills'),
  getAgents: () => apiFetch<SystemState['agents']>('/state/agents'),
  getMASystems: () => apiFetch<SystemState['ma_systems']>('/state/ma-systems'),
  getBridges: () => apiFetch<SystemState['bridges']>('/state/bridges'),
  getBudget: () => apiFetch<SystemState['budget']>('/state/budget'),
  getHealth: () => apiFetch<SystemState['health']>('/state/health'),
  getValidation: () => apiFetch<SystemState['validation']>('/state/validation'),
  refreshState: () => apiFetch<SystemState>('/state/refresh', { method: 'POST' }),
  checkHealth: () => apiFetch<{ status: string }>('/health'),
};
