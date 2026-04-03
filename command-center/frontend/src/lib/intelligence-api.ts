// Intelligence API client — activity timeline, audit log

import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api`;

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`Intel API error: ${res.status}`);
  return res.json();
}

// Activity types
export type ActivityCategory = 'execution' | 'protocol' | 'bridge' | 'lifecycle' | 'system' | 'memory';

export interface ActivityEntry {
  id: string;
  category: ActivityCategory;
  action: string;
  actor_type: string;
  actor_id: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  details: Record<string, unknown> | null;
  trace_id: string | null;
  timestamp: string;
}

export interface ActivityFilters {
  after?: string;
  before?: string;
  category?: ActivityCategory;
  actor?: string;
  entity_type?: string;
  entity_id?: string;
  action?: string;
  limit?: number;
  offset?: number;
}

export interface ActivityResponse {
  entries: ActivityEntry[];
  total: number;
  has_more: boolean;
}

export interface ActivityStats {
  by_category: Record<string, number>;
  by_actor: Record<string, number>;
  by_hour: Record<string, number>;
  total: number;
}

export interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface AuditResponse {
  entries: AuditEntry[];
  total: number;
}

export interface DecisionEntry {
  id: string;
  decision: string;
  action_taken: string;
  result: string;
  agent_id: string | null;
  context: Record<string, unknown>;
  timestamp: string;
}

// Activity
export async function fetchActivity(filters?: ActivityFilters): Promise<ActivityResponse> {
  const params = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    });
  }
  const qs = params.toString();
  return get(`${API}/activity/${qs ? `?${qs}` : ''}`);
}

export async function fetchActivityStats(): Promise<ActivityStats> {
  return get(`${API}/activity/stats`);
}

export async function fetchActivityCategories(): Promise<{ categories: { id: string; label: string; description: string }[] }> {
  return get(`${API}/activity/categories`);
}

// Decision log
export async function fetchDecisionLog(limit = 50): Promise<{ decisions: DecisionEntry[]; total: number }> {
  return get(`${API}/autonomous/decision-log?limit=${limit}`);
}

// Audit
export async function fetchAuditLog(limit = 50, action?: string): Promise<AuditResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (action) params.append('action', action);
  return get(`${API}/audit/log?${params}`);
}
