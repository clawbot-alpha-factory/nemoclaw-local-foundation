'use client';

import { create } from 'zustand';

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

export const useStore = create<AppStore>((set) => ({
  // ----- Initial state -----
  systemState: null,
  wsStatus: 'connecting',
  lastUpdate: null,
  stateVersion: 0,

  brainMessages: [],
  brainSidebarOpen: false,
  brainLoading: false,
  brainStatus: null,

  activeTab: 'home',

  circuitBreakers: {},
  activeConversationType: 'dm' as ConversationType,
  healthAlerts: [],

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
