import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api/ops`;

// --- Interfaces ---

export interface TaskCounts {
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  failed: number;
}

export interface BudgetSummary {
  total_budget_usd: number;
  spent_usd: number;
  remaining_usd: number;
}

export interface ActivitySummary {
  recent_count: number;
  last_activity_at: string | null;
}

export interface DashboardData {
  task_counts: TaskCounts;
  budget: BudgetSummary;
  activity: ActivitySummary;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  agent: string | null;
  skill: string | null;
  priority: 'critical' | 'high' | 'medium' | 'low';
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cost_usd: number | null;
  result: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
  page: number;
  page_size: number;
}

export interface TaskCreateInput {
  title: string;
  description?: string;
  agent?: string;
  skill?: string;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  metadata?: Record<string, unknown>;
}

export interface TaskUpdateInput {
  status?: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  agent?: string;
  priority?: 'critical' | 'high' | 'medium' | 'low';
  result?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface TaskFilters {
  status?: string;
  agent?: string;
  skill?: string;
  priority?: string;
  page?: number;
  page_size?: number;
}

export interface ProviderBudget {
  provider: string;
  spent_usd: number;
  allocated_usd: number;
  request_count: number;
  trend: number[];
  trend_labels: string[];
}

export interface BudgetBreakdown {
  total_budget_usd: number;
  total_spent_usd: number;
  total_remaining_usd: number;
  providers: ProviderBudget[];
}

export interface ActivityEntry {
  id: string;
  type: string;
  message: string;
  actor: string | null;
  task_id: string | null;
  timestamp: string;
  metadata: Record<string, unknown> | null;
}

export interface ActivityFeedResponse {
  activities: ActivityEntry[];
  total: number;
  page: number;
  page_size: number;
}

// --- API Functions ---

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.text().catch(() => 'Unknown error');
    throw new Error(`API error ${res.status}: ${errorBody}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API}/dashboard`, {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<DashboardData>(res);
}

export async function fetchTasks(filters?: TaskFilters): Promise<TaskListResponse> {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.status) params.set('status', filters.status);
    if (filters.agent) params.set('agent', filters.agent);
    if (filters.skill) params.set('skill', filters.skill);
    if (filters.priority) params.set('priority', filters.priority);
    if (filters.page !== undefined) params.set('page', String(filters.page));
    if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));
  }
  const query = params.toString();
  const url = `${API}/tasks${query ? `?${query}` : ''}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<TaskListResponse>(res);
}

export async function createTask(input: TaskCreateInput): Promise<Task> {
  const res = await fetch(`${API}/tasks`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Task>(res);
}

export async function updateTask(id: string, input: TaskUpdateInput): Promise<Task> {
  const res = await fetch(`${API}/tasks/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Task>(res);
}

export async function fetchBudget(): Promise<BudgetBreakdown> {
  const res = await fetch(`${API}/budget`, {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<BudgetBreakdown>(res);
}

export async function fetchActivity(page?: number, page_size?: number): Promise<ActivityFeedResponse> {
  const params = new URLSearchParams();
  if (page !== undefined) params.set('page', String(page));
  if (page_size !== undefined) params.set('page_size', String(page_size));
  const query = params.toString();
  const url = `${API}/activity${query ? `?${query}` : ''}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: headers(),
  });
  return handleResponse<ActivityFeedResponse>(res);
}