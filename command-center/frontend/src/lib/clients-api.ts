import { API_BASE } from './config';
const API = `${API_BASE}/api/clients`;

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface Client {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  industry?: string;
  status: 'active' | 'inactive' | 'prospect' | 'archived';
  tier?: 'enterprise' | 'professional' | 'starter';
  notes?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  address?: string;
  created_at: string;
  updated_at: string;
}

export interface ClientInput {
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  industry?: string;
  status?: 'active' | 'inactive' | 'prospect' | 'archived';
  tier?: 'enterprise' | 'professional' | 'starter';
  notes?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  address?: string;
}

export interface ClientUpdate {
  name?: string;
  email?: string;
  phone?: string;
  company?: string;
  industry?: string;
  status?: 'active' | 'inactive' | 'prospect' | 'archived';
  tier?: 'enterprise' | 'professional' | 'starter';
  notes?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  address?: string;
}

export interface Project {
  id: string;
  client_id: string;
  name: string;
  description?: string;
  status: 'active' | 'completed' | 'paused' | 'cancelled';
  start_date?: string;
  end_date?: string;
  budget?: number;
  created_at: string;
  updated_at: string;
}

export interface Deliverable {
  id: string;
  client_id: string;
  project_id?: string;
  name: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'approved' | 'rejected';
  due_date?: string;
  delivered_date?: string;
  type?: string;
  created_at: string;
  updated_at: string;
}

export interface DeliverableInput {
  name: string;
  project_id?: string;
  description?: string;
  status?: 'pending' | 'in_progress' | 'completed' | 'approved' | 'rejected';
  due_date?: string;
  delivered_date?: string;
  type?: string;
}

export interface ClientHealthScore {
  client_id: string;
  client_name: string;
  overall_score: number;
  engagement_score?: number;
  delivery_score?: number;
  satisfaction_score?: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  last_activity?: string;
  open_projects?: number;
  overdue_deliverables?: number;
}

export interface ClientListFilters {
  status?: string;
  tier?: string;
  industry?: string;
  search?: string;
  page?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ClientListResponse {
  items: Client[];
  total: number;
  page: number;
  limit: number;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.text();
    let message: string;
    try {
      const parsed = JSON.parse(errorBody);
      message = parsed.detail || parsed.message || errorBody;
    } catch {
      message = errorBody;
    }
    throw new Error(`API error ${res.status}: ${message}`);
  }
  return res.json();
}

export async function listClients(filters?: ClientListFilters): Promise<ClientListResponse> {
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
  return handleResponse<ClientListResponse>(res);
}

export async function createClient(data: ClientInput): Promise<Client> {
  const res = await fetch(`${API}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  });
  return handleResponse<Client>(res);
}

export async function getClient(id: string): Promise<Client> {
  const res = await fetch(`${API}/${id}`, { headers: headers() });
  return handleResponse<Client>(res);
}

export async function updateClient(id: string, data: ClientUpdate): Promise<Client> {
  const res = await fetch(`${API}/${id}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify(data),
  });
  return handleResponse<Client>(res);
}

export async function getClientProjects(id: string): Promise<Project[]> {
  const res = await fetch(`${API}/${id}/projects`, { headers: headers() });
  return handleResponse<Project[]>(res);
}

export async function getClientDeliverables(id: string): Promise<Deliverable[]> {
  const res = await fetch(`${API}/${id}/deliverables`, { headers: headers() });
  return handleResponse<Deliverable[]>(res);
}

export async function addClientDeliverable(id: string, data: DeliverableInput): Promise<Deliverable> {
  const res = await fetch(`${API}/${id}/deliverables`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(data),
  });
  return handleResponse<Deliverable>(res);
}

export async function getClientHealthScores(): Promise<ClientHealthScore[]> {
  const res = await fetch(`${API}/health`, { headers: headers() });
  return handleResponse<ClientHealthScore[]>(res);
}