import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api/approvals`;

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'escalated';
export type ApprovalPriority = 'critical' | 'high' | 'medium' | 'low';
export type ApprovalCategory = string;

export interface Approval {
  id: string;
  title: string;
  description: string;
  status: ApprovalStatus;
  priority: ApprovalPriority;
  category: ApprovalCategory;
  requester: string;
  assignee: string | null;
  notes: string | null;
  reason: string | null;
  escalated_to: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  metadata: Record<string, unknown>;
}

export interface ApprovalCreateInput {
  title: string;
  description: string;
  priority?: ApprovalPriority;
  category?: ApprovalCategory;
  requester?: string;
  assignee?: string;
  metadata?: Record<string, unknown>;
}

export interface ApproveInput {
  notes?: string;
}

export interface RejectInput {
  reason: string;
}

export interface EscalateInput {
  escalated_to: string;
  notes?: string;
}

export interface ApprovalListFilters {
  status?: ApprovalStatus;
  priority?: ApprovalPriority;
  category?: ApprovalCategory;
}

export interface AuditEntry {
  id: string;
  approval_id: string;
  action: string;
  actor: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface ApprovalListResponse {
  items: Approval[];
  total: number;
}

export interface AuditTrailResponse {
  items: AuditEntry[];
  total: number;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let message: string;
    try {
      const parsed = JSON.parse(body);
      message = parsed.detail || parsed.message || body;
    } catch {
      message = body;
    }
    throw new Error(`API error ${res.status}: ${message}`);
  }
  return res.json() as Promise<T>;
}

export async function listApprovals(filters?: ApprovalListFilters): Promise<ApprovalListResponse> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.priority) params.set('priority', filters.priority);
  if (filters?.category) params.set('category', filters.category);
  const query = params.toString();
  const url = query ? `${API}/?${query}` : `${API}/`;
  const res = await fetch(url, { headers: headers() });
  return handleResponse<ApprovalListResponse>(res);
}

export async function createApproval(input: ApprovalCreateInput): Promise<Approval> {
  const res = await fetch(`${API}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Approval>(res);
}

export async function getApprovalQueue(): Promise<Approval[]> {
  const res = await fetch(`${API}/queue`, { headers: headers() });
  return handleResponse<Approval[]>(res);
}

export async function getApproval(id: string): Promise<Approval> {
  const res = await fetch(`${API}/${id}`, { headers: headers() });
  return handleResponse<Approval>(res);
}

export async function approveApproval(id: string, input?: ApproveInput): Promise<Approval> {
  const res = await fetch(`${API}/${id}/approve`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input ?? {}),
  });
  return handleResponse<Approval>(res);
}

export async function rejectApproval(id: string, input: RejectInput): Promise<Approval> {
  const res = await fetch(`${API}/${id}/reject`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Approval>(res);
}

export async function escalateApproval(id: string, input: EscalateInput): Promise<Approval> {
  const res = await fetch(`${API}/${id}/escalate`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Approval>(res);
}

export async function getAuditTrail(): Promise<AuditTrailResponse> {
  const res = await fetch(`${API}/audit`, { headers: headers() });
  return handleResponse<AuditTrailResponse>(res);
}

// New endpoints matching backend rewrite

export async function fetchBlockers(): Promise<Approval[]> {
  const res = await fetch(`${API}/blockers`, { headers: headers() });
  return handleResponse<Approval[]>(res);
}

export async function fetchHistory(limit = 50, offset = 0): Promise<ApprovalListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const res = await fetch(`${API}/history?${params}`, { headers: headers() });
  return handleResponse<ApprovalListResponse>(res);
}

export interface ApprovalStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  escalated: number;
  blockers: number;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
}

export async function fetchApprovalStats(): Promise<ApprovalStats> {
  const res = await fetch(`${API}/stats`, { headers: headers() });
  return handleResponse<ApprovalStats>(res);
}

export interface BulkResult {
  succeeded: string[];
  failed: { id: string; error: string }[];
  total: number;
}

export async function bulkApprove(ids: string[], notes?: string): Promise<BulkResult> {
  const res = await fetch(`${API}/bulk/approve`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ ids, notes: notes || 'Bulk approved' }),
  });
  return handleResponse<BulkResult>(res);
}

export async function bulkReject(ids: string[], reason: string): Promise<BulkResult> {
  const res = await fetch(`${API}/bulk/reject`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ ids, reason }),
  });
  return handleResponse<BulkResult>(res);
}