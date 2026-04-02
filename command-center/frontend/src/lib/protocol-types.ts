// Protocol types for agent-to-agent communication, debates, brainstorms

export type ProtocolIntent =
  | 'inform' | 'challenge' | 'propose' | 'critique' | 'decide'
  | 'request' | 'acknowledge' | 'escalate' | 'delegate' | 'withdraw' | 'chat';

export type ChannelType = 'topic' | 'decision' | 'adversarial' | 'review' | 'direct';

export type ConversationType = 'dm' | 'agent-channel' | 'brainstorm' | 'debate' | 'group';

export type InteractionMode = 'brainstorm' | 'critique' | 'debate' | 'synthesis' | 'reflection';

export interface ProtocolMessage {
  id: string;
  sender: string;
  sender_name: string;
  channel_id: string;
  intent: ProtocolIntent;
  content: string;
  recipients: string[];
  references: string[];
  confidence: number;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface ProtocolHistoryResponse {
  messages: ProtocolMessage[];
  total: number;
}

export interface ProtocolInboxResponse {
  agent_id: string;
  messages: ProtocolMessage[];
  pending_count: number;
}

// Debates
export interface DebateRound {
  round: number;
  agent: string;
  agent_name: string;
  position: string;
  evidence: string[];
  timestamp: string;
}

export interface DebateSession {
  id: string;
  topic: string;
  agent_a: string;
  agent_a_name: string;
  agent_b: string;
  agent_b_name: string;
  status: 'active' | 'completed' | 'cancelled';
  rounds: DebateRound[];
  max_rounds: number;
  outcome: string | null;
  ruling_agent: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DebateListResponse {
  debates: DebateSession[];
  total: number;
}

// Brainstorms / Interaction Sessions
export interface BrainstormContribution {
  agent: string;
  agent_name: string;
  round: number;
  content: string;
  role: string;
  weight: number;
  timestamp: string;
}

export interface InteractionSession {
  session_id: string;
  mode: InteractionMode;
  topic: string;
  participants: string[];
  participant_names: string[];
  status: 'active' | 'complete' | 'cancelled';
  rounds_completed: number;
  max_rounds: number;
  contributions: BrainstormContribution[];
  output: Record<string, unknown> | null;
  conflicts: string[];
  lessons: string[];
  escalations: string[];
  started_at: string;
  completed_at: string | null;
}

export interface SessionListResponse {
  sessions: InteractionSession[];
  total: number;
}

// Start requests
export interface StartDebateRequest {
  topic: string;
  agent_a: string;
  agent_b: string;
  max_rounds?: number;
}

export interface StartSessionRequest {
  mode: InteractionMode;
  topic: string;
  participants: string[];
  max_rounds?: number;
}
