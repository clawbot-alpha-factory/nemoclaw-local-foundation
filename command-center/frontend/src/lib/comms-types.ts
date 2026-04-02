// ============================================================
// CC-3 COMMS TYPES — Add to src/lib/types.ts
// ============================================================

// Enums
export type MessageType = 'chat' | 'decision' | 'alert' | 'task' | 'approval' | 'system';
export type LaneType = 'dm' | 'group' | 'broadcast' | 'system';
export type SenderType = 'user' | 'agent' | 'system';

// Core Models
export interface CommsMessage {
  id: string;
  lane_id: string;
  message_type: MessageType;
  sender_id: string;
  sender_name: string;
  sender_type: SenderType;
  content: string;
  reply_to: string | null;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface Lane {
  id: string;
  name: string;
  lane_type: LaneType;
  participants: string[];
  avatar: string | null;
  last_message: CommsMessage | null;
  unread_count: number;
  created_at: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  avatar: string;
  lane_id: string;
}

// API Responses
export interface LaneListResponse {
  lanes: Lane[];
  total: number;
}

export interface MessageListResponse {
  messages: CommsMessage[];
  lane_id: string;
  total: number;
  has_more: boolean;
}

export interface SendMessageResponse {
  user_message: CommsMessage;
  agent_message?: CommsMessage | null;
  responder?: { id: string; name: string; role: string };
  agent_error?: string;
}
