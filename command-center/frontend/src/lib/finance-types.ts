// Finance types for budget tracking and cost governance

export interface ProviderBudgetDetail {
  provider: string;
  spent: number;
  limit: number;
  percent_used: number;
  currency: string;
  warn_threshold: number;
  hard_stop_threshold: number;
}

export interface AgentCostBreakdown {
  agent_id: string;
  agent_name: string;
  total_spent: number;
  call_count: number;
  avg_cost_per_call: number;
  by_provider: Record<string, number>;
}

export interface SkillCostBreakdown {
  skill_id: string;
  display_name: string;
  total_spent: number;
  execution_count: number;
  avg_cost_per_run: number;
  last_run: string | null;
}

export type CircuitBreakerState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export interface CircuitBreakerStatus {
  provider: string;
  state: CircuitBreakerState;
  trip_threshold: number;
  current_ratio: number;
  last_tripped: string | null;
  last_reset: string | null;
}

export interface UsageLogEntry {
  id: string;
  timestamp: string;
  provider: string;
  model: string;
  alias: string;
  task_class: string;
  agent_id: string | null;
  skill_id: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  duration_ms: number;
}

export interface UsageLogResponse {
  entries: UsageLogEntry[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface BudgetOverview {
  total_spent: number;
  total_limit: number;
  burn_rate_per_hour: number;
  projected_exhaustion: string | null;
  providers: ProviderBudgetDetail[];
  circuit_breakers: CircuitBreakerStatus[];
}
