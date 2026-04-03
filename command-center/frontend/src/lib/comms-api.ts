// ============================================================
// CC-3 COMMS API — src/lib/comms-api.ts
// ============================================================

import type {
  Lane,
  LaneListResponse,
  MessageListResponse,
  SendMessageResponse,
  MessageType,
  AgentInfo,
} from './comms-types';

import { API_BASE } from './config';
import { headers } from './auth';

// ------------------------------------------------------------------
// Lanes
// ------------------------------------------------------------------

export async function fetchLanes(): Promise<Lane[]> {
  const res = await fetch(`${API_BASE}/api/comms/lanes`, { headers: headers() });
  if (!res.ok) throw new Error(`Failed to fetch lanes: ${res.status}`);
  const data: LaneListResponse = await res.json();
  return data.lanes;
}

export async function fetchLane(laneId: string): Promise<Lane> {
  const res = await fetch(`${API_BASE}/api/comms/lanes/${laneId}`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to fetch lane: ${res.status}`);
  return res.json();
}

// ------------------------------------------------------------------
// Messages
// ------------------------------------------------------------------

export async function fetchMessages(
  laneId: string,
  limit = 50,
  before?: string
): Promise<MessageListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set('before', before);

  const res = await fetch(
    `${API_BASE}/api/comms/lanes/${laneId}/messages?${params}`,
    { headers: headers() }
  );
  if (!res.ok) throw new Error(`Failed to fetch messages: ${res.status}`);
  return res.json();
}

export async function sendMessage(
  laneId: string,
  content: string,
  messageType: MessageType = 'chat',
  metadata: Record<string, unknown> = {}
): Promise<SendMessageResponse> {
  const res = await fetch(`${API_BASE}/api/comms/lanes/${laneId}/send`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      content,
      message_type: messageType,
      metadata,
    }),
  });
  if (!res.ok) throw new Error(`Failed to send message: ${res.status}`);
  return res.json();
}

export async function markLaneRead(laneId: string): Promise<void> {
  await fetch(`${API_BASE}/api/comms/lanes/${laneId}/read`, {
    method: 'POST',
    headers: headers(),
  });
}

// ------------------------------------------------------------------
// Agents
// ------------------------------------------------------------------

export async function fetchAgents(): Promise<{
  agents: AgentInfo[];
  available: boolean;
}> {
  const res = await fetch(`${API_BASE}/api/comms/agents`, {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`Failed to fetch agents: ${res.status}`);
  return res.json();
}
