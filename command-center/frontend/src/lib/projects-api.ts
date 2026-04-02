// CC: Projects API client
import { API_BASE } from './config';
const API = `${API_BASE}/api/projects`;

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// --- Interfaces ---

export interface Milestone {
  id: string;
  title: string;
  description?: string;
  due_date?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'overdue';
  created_at: string;
  updated_at: string;
}

export interface MilestoneInput {
  title: string;
  description?: string;
  due_date?: string;
  status?: 'pending' | 'in_progress' | 'completed' | 'overdue';
}

export interface ProjectSkill {
  id: string;
  skill_id: string;
  display_name: string;
  description?: string;
  status: string;
  health: string;
  domain?: string;
  family?: string;
  assigned_agent?: string | null;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  status: 'planning' | 'active' | 'paused' | 'completed' | 'archived';
  priority: 'critical' | 'high' | 'medium' | 'low';
  owner?: string;
  tags?: string[];
  template_id?: string;
  milestones?: Milestone[];
  created_at: string;
  updated_at: string;
}

export interface ProjectInput {
  name: string;
  description?: string;
  status?: 'planning' | 'active' | 'paused' | 'completed' | 'archived';
  priority?: 'critical' | 'high' | 'medium' | 'low';
  owner?: string;
  tags?: string[];
  template_id?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: 'planning' | 'active' | 'paused' | 'completed' | 'archived';
  priority?: 'critical' | 'high' | 'medium' | 'low';
  owner?: string;
  tags?: string[];
}

export interface ProjectTemplate {
  id: string;
  name: string;
  description?: string;
  default_milestones?: MilestoneInput[];
  default_tags?: string[];
  category?: string;
}

export interface ProjectListFilters {
  status?: string;
  priority?: string;
  owner?: string;
  tag?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

// --- API Functions ---

export async function listProjects(filters?: ProjectListFilters): Promise<ProjectListResponse> {
  const params = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    });
  }
  const query = params.toString();
  const url = query ? `${API}/?${query}` : `${API}/`;

  const res = await fetch(url, { headers: headers() });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to list projects: ${res.status}`);
  }
  return res.json();
}

export async function createProject(input: ProjectInput): Promise<Project> {
  const res = await fetch(`${API}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to create project: ${res.status}`);
  }
  return res.json();
}

export async function listTemplates(): Promise<ProjectTemplate[]> {
  const res = await fetch(`${API}/templates`, { headers: headers() });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to list templates: ${res.status}`);
  }
  return res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API}/${id}`, { headers: headers() });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to get project: ${res.status}`);
  }
  return res.json();
}

export async function updateProject(id: string, input: ProjectUpdate): Promise<Project> {
  const res = await fetch(`${API}/${id}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to update project: ${res.status}`);
  }
  return res.json();
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API}/${id}`, {
    method: 'DELETE',
    headers: headers(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to delete project: ${res.status}`);
  }
}

export async function getProjectSkills(id: string): Promise<ProjectSkill[]> {
  const res = await fetch(`${API}/${id}/skills`, { headers: headers() });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to get project skills: ${res.status}`);
  }
  return res.json();
}

export async function addMilestone(projectId: string, input: MilestoneInput): Promise<Milestone> {
  const res = await fetch(`${API}/${projectId}/milestones`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to add milestone: ${res.status}`);
  }
  return res.json();
}

export async function updateMilestone(projectId: string, milestoneId: string, input: MilestoneInput): Promise<Milestone> {
  const res = await fetch(`${API}/${projectId}/milestones/${milestoneId}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to update milestone: ${res.status}`);
  }
  return res.json();
}

export async function deleteMilestone(projectId: string, milestoneId: string): Promise<void> {
  const res = await fetch(`${API}/${projectId}/milestones/${milestoneId}`, {
    method: 'DELETE',
    headers: headers(),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to delete milestone: ${res.status}`);
  }
}

// Lifecycle & team management
const ORCH_API = `${API_BASE}/api`;

export interface LifecycleStage {
  stage: string;
  status: 'pending' | 'active' | 'completed' | 'skipped';
  entered_at: string | null;
  completed_at: string | null;
  gate_passed: boolean;
}

export interface ProjectLifecycle {
  project_id: string;
  current_stage: string;
  stages: LifecycleStage[];
  created_at: string;
}

export interface TeamMember {
  agent_id: string;
  agent_name: string;
  role: string;
  assigned_at: string;
}

export interface ProjectTeam {
  project_id: string;
  members: TeamMember[];
  total: number;
}

export async function createWithLifecycle(input: ProjectInput & { service_type?: string }): Promise<Project> {
  const res = await fetch(`${ORCH_API}/projects/create-with-lifecycle`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Failed to create project with lifecycle: ${res.status}`);
  }
  return res.json();
}

export async function fetchProjectLifecycle(projectId: string): Promise<ProjectLifecycle> {
  const res = await fetch(`${ORCH_API}/projects/${projectId}/lifecycle`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch lifecycle: ${res.status}`);
  return res.json();
}

export async function advanceProjectStage(projectId: string): Promise<ProjectLifecycle> {
  const res = await fetch(`${ORCH_API}/projects/${projectId}/advance-stage`, {
    method: 'POST',
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to advance stage: ${res.status}`);
  return res.json();
}

export async function fetchProjectTeam(projectId: string): Promise<ProjectTeam> {
  const res = await fetch(`${ORCH_API}/projects/${projectId}/team`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch team: ${res.status}`);
  return res.json();
}

export async function assignAgentToProject(projectId: string, agentId: string, role: string): Promise<TeamMember> {
  const res = await fetch(`${ORCH_API}/projects/${projectId}/team/assign`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ agent_id: agentId, role }),
  });
  if (!res.ok) throw new Error(`Failed to assign agent: ${res.status}`);
  return res.json();
}

export async function fetchActiveProjects(): Promise<{ projects: Project[]; total: number }> {
  const res = await fetch(`${ORCH_API}/orchestrator/projects/active`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch active projects: ${res.status}`);
  return res.json();
}