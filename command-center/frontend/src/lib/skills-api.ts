// CC-5: Skills & Tools API client
import { API_BASE } from './config';
const API = `${API_BASE}/api/skills`;

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface SkillInput {
  name: string;
  type?: string;
  required?: boolean;
  default?: string;
  description?: string;
  validation?: Record<string, number>;
}

export interface SkillStep {
  id: string;
  name: string;
  step_type: string;
  task_class: string;
}

export interface Skill {
  id: string;
  display_name: string;
  description: string;
  version: string;
  status: 'built' | 'registered';
  health: 'healthy' | 'missing_dependencies' | 'misconfigured' | 'unused' | 'not_built';
  health_reason: string;
  domain: string;
  family: string;
  skill_type: string;
  tag: string;
  schema_version: number;
  assigned_agent: string | null;
  priority: 'critical' | 'high' | 'medium' | 'low';
  inputs: SkillInput[];
  outputs: { name: string; type: string; description: string }[];
  composable: {
    output_type: string;
    feeds_into: string[];
    accepts_from: string[];
  };
  contracts: {
    max_cost_usd?: number;
    max_execution_seconds?: number;
    min_quality_score?: number;
  };
  steps: SkillStep[];
  routing: string;
  execution_role: string;
  declarative_guarantees: string[];
}

export interface SkillStats {
  total: number;
  by_status: Record<string, number>;
  by_domain: Record<string, number>;
  by_priority: Record<string, number>;
  by_health: Record<string, number>;
  by_type: Record<string, number>;
  by_agent: Record<string, number>;
  graph: {
    total_edges: number;
    circular_deps: number;
    orphans: number;
    overloaded: number;
  };
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphNode {
  id: string;
  display_name: string;
  status: string;
  domain: string;
  family: string;
  skill_type: string;
  priority: string;
  health: string;
  assigned_agent: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  risks: {
    circular: string[][];
    orphans: string[];
    overloaded: string[];
  };
  stats: {
    total_nodes: number;
    total_edges: number;
    circular_count: number;
    orphan_count: number;
    overloaded_count: number;
  };
}

export interface DryRunResult {
  skill_id: string;
  display_name: string;
  passed: boolean;
  errors?: string[];
  warnings?: string[];
  error?: string;
  input_schema: SkillInput[];
  provided_inputs: Record<string, string>;
  dependency_chain: {
    upstream: { id: string; display_name: string; status: string }[];
    downstream: { id: string; display_name: string; status: string }[];
  };
  dependency_health?: {
    all_available: boolean;
    missing: string[];
    unhealthy: string[];
  };
  estimated_cost?: string;
  estimated_time?: string;
  output_structure?: { name: string; type: string; description: string }[];
  steps?: SkillStep[];
  routing?: string;
  health?: string;
  priority?: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: headers() });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchSkills(params?: Record<string, string>): Promise<{ total: number; skills: Skill[] }> {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return get(`/${qs}`);
}

export async function fetchSkillStats(): Promise<SkillStats> {
  return get('/stats');
}

export async function fetchSkillGraph(): Promise<GraphData> {
  return get('/graph');
}

export async function fetchSkillsByAgent(agentId: string): Promise<{ agent_id: string; total: number; primary: Skill[]; future: Skill[] }> {
  return get(`/agents/${agentId}`);
}

export async function fetchSkill(skillId: string): Promise<Skill> {
  return get(`/${skillId}`);
}

export async function dryRunSkill(skillId: string, inputs: Record<string, string>): Promise<DryRunResult> {
  const res = await fetch(`${API}/${skillId}/dry-run`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ inputs }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function reloadSkills(): Promise<{ status: string; total: number }> {
  const res = await fetch(`${API}/reload`, {
    method: 'POST',
    headers: headers(),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Skill execution history
export interface SkillExecution {
  id: string;
  skill_id: string;
  status: 'completed' | 'failed' | 'running';
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  cost_usd: number | null;
  agent_id: string | null;
  error: string | null;
}

export async function fetchSkillHistory(skillId: string, limit = 20): Promise<{ executions: SkillExecution[]; total: number }> {
  return get(`/${skillId}/history?limit=${limit}`);
}
