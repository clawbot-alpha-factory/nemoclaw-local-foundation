// Protocol API client — agent-to-agent messaging, debates, interaction sessions
import type {
  ProtocolHistoryResponse,
  ProtocolInboxResponse,
  DebateSession,
  DebateListResponse,
  SessionListResponse,
  InteractionSession,
  StartDebateRequest,
  StartSessionRequest,
} from './protocol-types';

import { API_BASE } from './config';
import { headers } from './auth';
const API = `${API_BASE}/api`;

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`Protocol API error: ${res.status}`);
  return res.json();
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Protocol API error: ${res.status}`);
  return res.json();
}

// Protocol messages
export async function fetchProtocolHistory(limit = 100): Promise<ProtocolHistoryResponse> {
  return get(`${API}/protocol/history?limit=${limit}`);
}

export async function fetchProtocolInbox(agentId: string): Promise<ProtocolInboxResponse> {
  return get(`${API}/protocol/inbox/${agentId}`);
}

// Debates
export async function fetchDebates(): Promise<DebateListResponse> {
  return get(`${API}/debate/list`);
}

export async function fetchDebate(debateId: string): Promise<DebateSession> {
  return get(`${API}/debate/${debateId}`);
}

export async function startDebate(request: StartDebateRequest): Promise<DebateSession> {
  return post(`${API}/debate/start`, request);
}

// Interaction sessions (brainstorm, critique, synthesis, reflection)
export async function fetchSessions(): Promise<SessionListResponse> {
  return get(`${API}/protocol/sessions`);
}

export async function fetchSession(sessionId: string): Promise<InteractionSession> {
  return get(`${API}/protocol/sessions/${sessionId}`);
}

export async function startSession(request: StartSessionRequest): Promise<InteractionSession> {
  return post(`${API}/protocol/sessions/start`, request);
}

// Workspace
export async function fetchWorkspace(workspaceId: string, namespace?: string): Promise<Record<string, unknown>> {
  const params = namespace ? `?namespace=${namespace}` : '';
  return get(`${API}/workspace/${workspaceId}/read${params}`);
}
