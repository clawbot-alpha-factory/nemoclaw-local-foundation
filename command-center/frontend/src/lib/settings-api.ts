// CC: Settings API client
import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api/settings`;

export interface ThemePreference {
  theme: 'light' | 'dark';
}

export interface ActiveToken {
  token: string;
  created_at?: string;
  expires_at?: string | null;
}

export interface GitInfo {
  branch: string;
  commit: string;
  dirty: boolean;
}

export interface SystemInfo {
  python_version: string;
  node_version: string;
  git: GitInfo;
  uptime: number | { seconds: number; hours: number };
  uptime_human: string;
}

export interface BrainInterval {
  interval: number;
}

export interface Settings {
  token: string;
  theme: 'light' | 'dark';
  intervals: {
    brain?: number;
    brain_interval?: number;
  };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.text().catch(() => 'Unknown error');
    throw new Error(`API error ${response.status}: ${errorBody}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchSettings(): Promise<Settings> {
  const response = await fetch(API + '/', {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<Settings>(response);
}

export async function fetchToken(): Promise<ActiveToken> {
  const response = await fetch(API + '/token', {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<ActiveToken>(response);
}

export async function setTheme(theme: 'light' | 'dark'): Promise<ThemePreference> {
  const response = await fetch(API + '/theme', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ theme }),
  });
  return handleResponse<ThemePreference>(response);
}

export async function fetchSystemInfo(): Promise<SystemInfo> {
  const response = await fetch(API + '/system', {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<SystemInfo>(response);
}

export async function updateBrainInterval(interval: number): Promise<BrainInterval> {
  const response = await fetch(API + '/brain/interval', {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ interval }),
  });
  return handleResponse<BrainInterval>(response);
}

// API Keys
export interface ApiKeyInfo {
  provider: string;
  configured: boolean;
  masked_key: string | null;
  last_tested: string | null;
  status: 'connected' | 'missing' | 'invalid';
}

export async function fetchApiKeys(): Promise<{ keys: ApiKeyInfo[] }> {
  const response = await fetch(API + '/api-keys', { method: 'GET', headers: headers() });
  return handleResponse<{ keys: ApiKeyInfo[] }>(response);
}

export async function updateApiKey(provider: string, key: string): Promise<{ status: string }> {
  const response = await fetch(`${API}/api-keys/${provider}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ key }),
  });
  return handleResponse<{ status: string }>(response);
}

export async function testApiKey(provider: string): Promise<{ provider: string; success: boolean; error?: string }> {
  const response = await fetch(`${API}/api-keys/${provider}/test`, {
    method: 'POST',
    headers: headers(),
  });
  return handleResponse<{ provider: string; success: boolean; error?: string }>(response);
}

// Model Library
export interface ModelAlias {
  alias: string;
  provider: string;
  model: string;
  cost_per_call: number;
  max_tokens: number;
  description: string;
}

export interface RoutingRule {
  task_class: string;
  alias: string;
  description: string;
}

export async function fetchModelLibrary(): Promise<{ aliases: ModelAlias[] }> {
  const response = await fetch(API + '/models', { method: 'GET', headers: headers() });
  return handleResponse<{ aliases: ModelAlias[] }>(response);
}

export async function fetchRoutingRules(): Promise<{ rules: RoutingRule[]; default_alias: string }> {
  const response = await fetch(API + '/routing-rules', { method: 'GET', headers: headers() });
  return handleResponse<{ rules: RoutingRule[]; default_alias: string }>(response);
}

// Bridges
const BRIDGE_API = `${API_BASE}/api/bridges`;

export interface BridgeInfo {
  id: string;
  name: string;
  status: 'connected' | 'mocked' | 'error' | 'unconfigured';
  has_api_key: boolean;
  enabled: boolean;
  last_health_check: string | null;
  call_count: number;
}

export async function fetchBridgeStatus(): Promise<{ bridges: BridgeInfo[] }> {
  const response = await fetch(`${BRIDGE_API}/status`, { method: 'GET', headers: headers() });
  return handleResponse<{ bridges: BridgeInfo[] }>(response);
}

export async function runBridgeHealthCheck(bridgeId: string): Promise<{ status: string; details: Record<string, unknown> }> {
  const response = await fetch(`${BRIDGE_API}/${bridgeId}/health`, {
    method: 'POST',
    headers: headers(),
  });
  return handleResponse<{ status: string; details: Record<string, unknown> }>(response);
}