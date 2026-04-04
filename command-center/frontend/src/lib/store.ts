'use client';

import { create } from 'zustand';

// ── Persistence helpers ──────────────────────────────────────────────
const PERSIST_KEY = 'nc-store';

function loadPersistedState(): Partial<AppStore> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(PERSIST_KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    return {
      activeTab: data.activeTab || 'home',
      brainMessages: data.brainMessages || [],
      brainSidebarOpen: data.brainSidebarOpen || false,
      healthAlerts: data.healthAlerts || [],
      activeConversationType: data.activeConversationType || 'dm',
    };
  } catch { return {}; }
}

function persistState(state: Partial<AppStore>) {
  if (typeof window === 'undefined') return;
  try {
    const data = {
      activeTab: state.activeTab,
      brainMessages: (state.brainMessages || []).slice(-50), // keep last 50
      brainSidebarOpen: state.brainSidebarOpen,
      healthAlerts: (state.healthAlerts || []).slice(-20),
      activeConversationType: state.activeConversationType,
    };
    localStorage.setItem(PERSIST_KEY, JSON.stringify(data));
  } catch { /* quota exceeded — silently fail */ }
}

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

export interface BrainMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  type: 'question' | 'response' | 'insight' | 'error' | 'status';
}

export interface BrainStatus {
  available: boolean;
  provider: string;
  model: string;
  alias: string;
  history_length: number;
}

export type ConversationType = 'dm' | 'agent-channel' | 'brainstorm' | 'debate' | 'group';

export interface HealthAlert {
  id: string;
  domain: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  timestamp: string;
}

// ------------------------------------------------------------------
// Store
// ------------------------------------------------------------------

interface AppStore {
  // System state (from WebSocket)
  systemState: any | null;
  wsStatus: 'connecting' | 'connected' | 'disconnected';
  lastUpdate: Date | null;
  stateVersion: number;

  // Brain sidebar
  brainMessages: BrainMessage[];
  brainSidebarOpen: boolean;
  brainLoading: boolean;
  brainStatus: BrainStatus | null;

  // Navigation
  activeTab: string;

  // Finance
  circuitBreakers: Record<string, { tripped: boolean; provider: string }>;

  // Communications
  activeConversationType: ConversationType;

  // Health alerts
  healthAlerts: HealthAlert[];

  // System state actions
  setSystemState: (state: any) => void;
  setWsStatus: (status: 'connecting' | 'connected' | 'disconnected') => void;
  setLastUpdate: (date: Date) => void;
  setStateVersion: (version: number) => void;

  // Brain actions
  addBrainMessage: (msg: BrainMessage) => void;
  setBrainLoading: (loading: boolean) => void;
  setBrainStatus: (status: BrainStatus) => void;
  toggleBrainSidebar: () => void;
  setBrainSidebarOpen: (open: boolean) => void;
  clearBrainHistory: () => void;

  // Navigation actions
  setActiveTab: (tab: string) => void;

  // Finance actions
  setCircuitBreakers: (breakers: Record<string, { tripped: boolean; provider: string }>) => void;

  // Communications actions
  setConversationType: (type: ConversationType) => void;

  // Health alert actions
  addHealthAlert: (alert: HealthAlert) => void;
  clearHealthAlerts: () => void;
}

const _persisted = loadPersistedState();

export const useStore = create<AppStore>((set) => ({
  // ----- Initial state (merge with persisted) -----
  systemState: null,
  wsStatus: 'connecting',
  lastUpdate: null,
  stateVersion: 0,

  brainMessages: _persisted.brainMessages || [],
  brainSidebarOpen: _persisted.brainSidebarOpen || false,
  brainLoading: false,
  brainStatus: null,

  activeTab: _persisted.activeTab || 'home',

  circuitBreakers: {},
  activeConversationType: (_persisted.activeConversationType as ConversationType) || 'dm',
  healthAlerts: _persisted.healthAlerts || [],

  // ----- System state actions -----
  setSystemState: (state) => set({ systemState: state }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setLastUpdate: (date) => set({ lastUpdate: date }),
  setStateVersion: (version) => set({ stateVersion: version }),

  // ----- Brain actions -----
  addBrainMessage: (msg) =>
    set((s) => ({
      brainMessages: [...s.brainMessages, msg],
    })),

  setBrainLoading: (loading) => set({ brainLoading: loading }),

  setBrainStatus: (status) => set({ brainStatus: status }),

  toggleBrainSidebar: () =>
    set((s) => ({ brainSidebarOpen: !s.brainSidebarOpen })),

  setBrainSidebarOpen: (open) => set({ brainSidebarOpen: open }),

  clearBrainHistory: () => set({ brainMessages: [] }),

  // ----- Navigation -----
  setActiveTab: (tab) => set({ activeTab: tab }),

  // ----- Finance -----
  setCircuitBreakers: (breakers) => set({ circuitBreakers: breakers }),

  // ----- Communications -----
  setConversationType: (type) => set({ activeConversationType: type }),

  // ----- Health alerts -----
  addHealthAlert: (alert) =>
    set((s) => ({
      healthAlerts: [...s.healthAlerts.slice(-99), alert],
    })),
  clearHealthAlerts: () => set({ healthAlerts: [] }),
}));

// Auto-persist selected state to localStorage on every change
useStore.subscribe((state) => {
  persistState(state);
});
