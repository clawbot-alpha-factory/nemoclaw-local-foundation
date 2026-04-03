// ============================================================
// CC-4 AGENTS API — src/lib/agents-api.ts
// ============================================================

import { API_BASE } from './config';
import { headers } from './auth';

export interface AgentSkills {
  primary: string[];
  future: string[];
  primary_count: number;
  future_count: number;
  total: number;
}

export interface AgentActivity {
  total_messages: number;
  messages_24h: number;
  conversations: number;
  conversations_24h: number;
  avg_response_seconds: number | null;
  broadcast_messages: number;
  last_active: string | null;
  status: 'active' | 'recent' | 'idle';
}

export interface AgentProfile {
  id: string;
  name: string;
  character_name: string;
  character: string;
  role_display: string;
  title: string;
  role: string;
  avatar: string;
  lane_id: string;
  authority_level: number;
  capabilities: string[];
  decides: string[];
  skills: AgentSkills;
  failure_modes: string[];
  metrics_tracked: string[];
  memory_access: Record<string, string>;
  constraints: string[];
  family: string;
  activity?: AgentActivity;
}

export interface OrgLevel {
  level: number;
  label: string;
  agents: { id: string; name: string; title: string; avatar: string; authority_level: number }[];
}

export interface WorkloadEntry {
  id: string;
  name: string;
  avatar: string;
  title: string;
  status: string;
  messages_24h: number;
  avg_response_seconds: number | null;
  total_messages: number;
  skills_assigned: number;
  capabilities_count: number;
}

export async function fetchAgentProfiles(): Promise<{ agents: AgentProfile[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/agents/`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch agents: ${res.status}`);
  return res.json();
}

export async function fetchAgent(id: string): Promise<AgentProfile> {
  const res = await fetch(`${API_BASE}/api/agents/${id}`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch agent: ${res.status}`);
  return res.json();
}

export async function fetchOrgHierarchy(): Promise<{ hierarchy: OrgLevel[] }> {
  const res = await fetch(`${API_BASE}/api/agents/org`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch org: ${res.status}`);
  return res.json();
}

export async function fetchWorkload(): Promise<{ team: WorkloadEntry[]; summary: { total_agents: number; active_now: number; total_messages: number } }> {
  const res = await fetch(`${API_BASE}/api/agents/workload`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch workload: ${res.status}`);
  return res.json();
}

// Agent loop control
export interface LoopStatus {
  agent_id: string;
  running: boolean;
  iteration_count: number;
  last_action: string | null;
  last_error: string | null;
  started_at: string | null;
}

export interface AgentMemoryEntry {
  key: string;
  value: unknown;
  memory_type: string;
  importance: number;
  source: string;
  timestamp: string;
}

export interface PerformanceDimension {
  dimension: string;
  score: number;
  sample_count: number;
  trend: 'up' | 'down' | 'stable';
}

export interface AgentPerformance {
  agent_id: string;
  composite_score: number;
  dimensions: PerformanceDimension[];
  alert_level: 'normal' | 'watch' | 'warning' | 'critical';
  last_updated: string;
}

export async function fetchLoopStatus(agentId: string): Promise<LoopStatus> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/loop-status`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch loop status: ${res.status}`);
  return res.json();
}

export async function fetchAgentMemory(agentId: string): Promise<{ lessons: AgentMemoryEntry[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/memory`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch agent memory: ${res.status}`);
  return res.json();
}

export async function fetchAgentPerformance(agentId: string): Promise<AgentPerformance> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/performance`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch agent performance: ${res.status}`);
  return res.json();
}

export async function startAgentLoop(agentId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/start`, {
    method: 'POST',
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to start agent: ${res.status}`);
  return res.json();
}

export async function stopAgentLoop(agentId: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/stop`, {
    method: 'POST',
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to stop agent: ${res.status}`);
  return res.json();
}
