'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

// CC-2: AI Brain
import { useStore } from '../lib/store';
import type { SystemState } from '@/lib/types';
import { WS_BASE, API_BASE } from '@/lib/config';

const WS_URL = `${WS_BASE}/ws`;
const WS_CHAT_URL = `${WS_BASE}/ws/chat`;
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_DELAY = 30000;

// ── REST fallback: fetch state when WS is unavailable ──
async function fetchStateViaRest(token: string): Promise<SystemState | null> {
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/api/state`, { headers });
    if (res.ok) {
      const data = await res.json();
      return data as SystemState;
    }
  } catch { /* fallback silently */ }
  return null;
}

// ── Auto-resolve token: try API /api/settings/token, then known local token ──
async function resolveToken(): Promise<string> {
  const stored = typeof window !== 'undefined' ? localStorage.getItem('cc-token') || '' : '';
  if (stored) return stored;

  // Try fetching token from settings API (unauthenticated endpoint on local)
  try {
    const res = await fetch(`${API_BASE}/api/settings/token`);
    if (res.ok) {
      const data = await res.json();
      const token = data?.token || '';
      if (token && typeof window !== 'undefined') {
        localStorage.setItem('cc-token', token);
      }
      return token;
    }
  } catch { /* ignore */ }

  return stored;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketReturn {
  state: SystemState | null;
  status: ConnectionStatus;
  lastUpdate: Date | null;
  refresh: () => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const [state, setState] = useState<SystemState | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const chatWsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(RECONNECT_DELAY);
  const chatReconnectDelay = useRef(RECONNECT_DELAY);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const chatReconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const lastVersion = useRef(0);

  // REST polling fallback when WS is unavailable
  const restPollRef = useRef<ReturnType<typeof setInterval>>();
  const tokenRef = useRef<string>('');

  const startRestPolling = useCallback((token: string) => {
    if (restPollRef.current) return; // already polling
    const poll = async () => {
      const s = await fetchStateViaRest(token);
      if (s) {
        setState(s);
        setLastUpdate(new Date());
        if (status === 'connecting') setStatus('connected');
      }
    };
    poll(); // immediate first fetch
    restPollRef.current = setInterval(poll, 10000); // poll every 10s
  }, [status]);

  const stopRestPolling = useCallback(() => {
    if (restPollRef.current) {
      clearInterval(restPollRef.current);
      restPollRef.current = undefined;
    }
  }, []);

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = await resolveToken();
    tokenRef.current = token;

    const url = token ? `${WS_URL}?token=${token}` : WS_URL;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      setStatus('connected');
      reconnectDelay.current = RECONNECT_DELAY;
      stopRestPolling(); // WS is live, no need for REST polling
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        // Brain insight (auto-generated)
        if (msg?.type === 'brain_insight' && msg?.data) {
          const store = useStore.getState();
          store.addBrainMessage({
            role: 'assistant',
            content: msg.data.content,
            timestamp: msg.data.timestamp,
            type: 'insight',
          });
          return;
        }

        // Budget alert (circuit breaker trip, spend warning)
        if (msg?.type === 'budget_alert' && msg?.data) {
          const store = useStore.getState();
          store.addHealthAlert({
            id: `budget-${Date.now()}`,
            domain: 'budget',
            severity: msg.data.severity || 'warning',
            message: msg.data.message || 'Budget alert',
            timestamp: new Date().toISOString(),
          });
          if (msg.data.circuit_breakers) {
            const breakers: Record<string, { tripped: boolean; provider: string }> = {};
            for (const cb of msg.data.circuit_breakers) {
              breakers[cb.provider] = { tripped: cb.state === 'OPEN', provider: cb.provider };
            }
            store.setCircuitBreakers(breakers);
          }
          return;
        }

        // Health alert
        if (msg?.type === 'health_alert' && msg?.data) {
          const store = useStore.getState();
          store.addHealthAlert({
            id: `health-${Date.now()}`,
            domain: msg.data.domain || 'system',
            severity: msg.data.severity || 'warning',
            message: msg.data.message || 'Health alert',
            timestamp: new Date().toISOString(),
          });
          return;
        }

        // State update
        if (msg?.type === 'state_update' && msg?.payload) {
          const incoming = msg.payload as unknown as SystemState;
          if (incoming.state_version >= lastVersion.current) {
            lastVersion.current = incoming.state_version;
            setState(incoming);
            setLastUpdate(new Date());
          }
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      startRestPolling(tokenRef.current); // fallback to REST while WS reconnects
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(
          reconnectDelay.current * 1.5,
          MAX_RECONNECT_DELAY
        );
        connect();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      setStatus('error');
      startRestPolling(tokenRef.current); // fallback to REST on error
    };
  }, [startRestPolling, stopRestPolling]);

  const connectChat = useCallback(async () => {
    if (chatWsRef.current?.readyState === WebSocket.OPEN) return;

    const token = tokenRef.current || await resolveToken();

    const url = token ? `${WS_CHAT_URL}?token=${token}` : WS_CHAT_URL;
    const ws = new WebSocket(url);
    chatWsRef.current = ws;

    ws.onopen = () => {
      chatReconnectDelay.current = RECONNECT_DELAY;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'chat_message' && data.data) {
          window.dispatchEvent(
            new CustomEvent('cc-chat-message', { detail: data.data })
          );
        } else if (data.type === 'chat_chunk' && data.data) {
          window.dispatchEvent(
            new CustomEvent('cc-chat-chunk', { detail: data.data })
          );
        } else if (data.type === 'chat_complete' && data.data) {
          window.dispatchEvent(
            new CustomEvent('cc-chat-complete', { detail: data.data })
          );
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onclose = () => {
      chatWsRef.current = null;
      chatReconnectTimer.current = setTimeout(() => {
        chatReconnectDelay.current = Math.min(
          chatReconnectDelay.current * 1.5,
          MAX_RECONNECT_DELAY
        );
        connectChat();
      }, chatReconnectDelay.current);
    };

    ws.onerror = (e) => {
      console.error('WS parse error:', e);
    };
  }, []);

  const refresh = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('refresh');
    }
  }, []);

  useEffect(() => {
    connect();
    connectChat();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (chatReconnectTimer.current) clearTimeout(chatReconnectTimer.current);
      stopRestPolling();
      wsRef.current?.close();
      chatWsRef.current?.close();
    };
  }, [connect, connectChat, stopRestPolling]);

  return { state, status, lastUpdate, refresh };
}
