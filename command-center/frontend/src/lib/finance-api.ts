// Finance API client — budget tracking, cost governance
import type {
  BudgetOverview,
  AgentCostBreakdown,
  SkillCostBreakdown,
  CircuitBreakerStatus,
  UsageLogResponse,
} from './finance-types';

import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api/ops`;

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`Finance API error: ${res.status}`);
  return res.json();
}

export async function fetchBudgetOverview(period?: string): Promise<BudgetOverview> {
  const params = period ? `?period=${period}` : '';
  const raw = await get<Record<string, unknown>>(`${API}/budget${params}`);

  // Normalize backend shape to BudgetOverview
  const totalSpent = (raw.total_spent as number) || 0;
  const totalLimit = (raw.total_budget as number) || (raw.total_limit as number) || 90;
  const byProvider = raw.by_provider as Record<string, unknown> || {};

  // Convert by_provider object to array
  const providers: BudgetOverview['providers'] = Object.entries(byProvider).map(([provider, data]) => {
    const d = (data || {}) as Record<string, number>;
    return {
      provider,
      spent: d.spent || 0,
      limit: d.limit || 30,
      percent_used: d.percent_used || (d.limit ? (d.spent / d.limit) * 100 : 0),
      currency: 'USD',
      warn_threshold: 90,
      hard_stop_threshold: 100,
    };
  });

  // If no providers from backend, create defaults from budget-config
  if (providers.length === 0) {
    for (const name of ['anthropic', 'openai', 'google']) {
      providers.push({
        provider: name,
        spent: 0,
        limit: 30,
        percent_used: 0,
        currency: 'USD',
        warn_threshold: 90,
        hard_stop_threshold: 100,
      });
    }
  }

  return {
    total_spent: totalSpent,
    total_limit: totalLimit,
    burn_rate_per_hour: (raw.daily_burn_rate as number || 0) / 24,
    projected_exhaustion: raw.days_remaining
      ? new Date(Date.now() + (raw.days_remaining as number) * 86400000).toISOString()
      : null,
    providers,
    circuit_breakers: providers.map(p => ({
      provider: p.provider,
      state: 'CLOSED' as const,
      trip_threshold: 1.5,
      current_ratio: p.percent_used / 100,
      last_tripped: null,
      last_reset: null,
    })),
  };
}

export async function fetchBudgetByAgent(): Promise<{ agents: AgentCostBreakdown[]; total: number }> {
  return get(`${API}/budget/by-agent`);
}

export async function fetchBudgetBySkill(): Promise<{ skills: SkillCostBreakdown[]; total: number }> {
  return get(`${API}/budget/by-skill`);
}

export async function fetchCircuitBreakers(): Promise<{ breakers: CircuitBreakerStatus[] }> {
  return get(`${API}/budget/circuit-breaker`);
}

export async function fetchUsageLog(page = 1, pageSize = 50): Promise<UsageLogResponse> {
  return get(`${API}/budget/usage-log?page=${page}&page_size=${pageSize}`);
}
