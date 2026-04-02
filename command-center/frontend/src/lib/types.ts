/**
 * Command Center TypeScript types.
 * Mirrors the backend Pydantic models exactly.
 */

export type HealthStatus = 'healthy' | 'warning' | 'error' | 'unknown';
export type SkillStatus = 'built' | 'registered' | 'failed';
export type BridgeStatus = 'connected' | 'mocked' | 'error' | 'unconfigured';
export type WSMessageType = 'state_update' | 'health_alert' | 'error' | 'connected';

export interface SkillInfo {
  skill_id: string;
  family: string;
  name: string;
  status: SkillStatus;
  provider: string;
  last_run: string | null;
  validation_score: string;
}

export interface SkillsSummary {
  total_built: number;
  total_registered: number;
  skills: SkillInfo[];
  families: Record<string, number>;
}

export interface AgentInfo {
  agent_id: string;
  name: string;
  role: string;
  capabilities: string[];
  domains: string[];
  status: HealthStatus;
}

export interface AgentsSummary {
  total: number;
  agents: AgentInfo[];
}

export interface MASystemInfo {
  system_id: string;
  name: string;
  test_count: number;
  status: HealthStatus;
}

export interface MASummary {
  total: number;
  total_tests: number;
  systems: MASystemInfo[];
}

export interface BridgeInfo {
  bridge_id: string;
  name: string;
  api: string;
  test_count: number;
  test_pass: number;
  status: BridgeStatus;
  has_api_key: boolean;
}

export interface BridgesSummary {
  total: number;
  total_tests: number;
  connected: number;
  bridges: BridgeInfo[];
}

export interface ProviderBudget {
  provider: string;
  spent: number;
  limit: number;
  percent_used: number;
  currency: string;
}

export interface BudgetSummary {
  total_spent: number;
  total_limit: number;
  providers: ProviderBudget[];
}

export interface HealthDomain {
  domain: string;
  status: HealthStatus;
  message: string;
  last_check: string | null;
}

export interface HealthSummary {
  overall: HealthStatus;
  domains: HealthDomain[];
}

export interface ValidationSummary {
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
}

export interface FrameworksSummary {
  total: number;
  framework_ids: string[];
}

export interface SystemState {
  timestamp: string;
  state_version: number;
  version: string;
  skills: SkillsSummary;
  agents: AgentsSummary;
  ma_systems: MASummary;
  bridges: BridgesSummary;
  budget: BudgetSummary;
  health: HealthSummary;
  validation: ValidationSummary;
  frameworks: FrameworksSummary;
  narrative: string[];
  repo_root: string;
  git_branch: string;
  git_commit: string;
  pinchtab_status: string;
}

export interface WSMessage {
  type: WSMessageType;
  payload: Record<string, unknown>;
  timestamp: string;
}

// Tab definitions for navigation
export type TabId =
  | 'home'
  | 'communications'
  | 'agents'
  | 'skills'
  | 'operations'
  | 'finance'
  | 'marketing'
  | 'projects'
  | 'clients'
  | 'approvals'
  | 'intelligence'
  | 'research'
  | 'settings'
  | 'execution'
  | 'playground';

export interface TabDef {
  id: TabId;
  label: string;
  icon: string;
  badge?: number;
  disabled?: boolean;
}
