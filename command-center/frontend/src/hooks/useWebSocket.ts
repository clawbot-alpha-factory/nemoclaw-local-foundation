'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { SystemState, WSMessage } from '@/lib/types';

const WS_URL = 'ws://127.0.0.1:8100/ws';
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_DELAY = 30000;

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
  const reconnectDelay = useRef(RECONNECT_DELAY);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const lastVersion = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = typeof window !== 'undefined'
      ? localStorage.getItem('cc-token') || ''
      : '';

    const url = token ? `${WS_URL}?token=${token}` : WS_URL;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      setStatus('connected');
      reconnectDelay.current = RECONNECT_DELAY;
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === 'state_update' && msg.payload) {
          const incoming = msg.payload as unknown as SystemState;
          // Monotonic version check — never apply stale state
          if (incoming.state_version >= lastVersion.current) {
            lastVersion.current = incoming.state_version;
            setState(incoming);
            setLastUpdate(new Date());
          }
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;

      // Auto-reconnect with backoff
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
    };
  }, []);

  const refresh = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('refresh');
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { state, status, lastUpdate, refresh };
}
