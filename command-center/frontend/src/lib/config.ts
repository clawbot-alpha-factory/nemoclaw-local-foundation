// Centralized API configuration — single source of truth for all endpoints
const rawBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8100';

// Strip trailing slash
export const API_BASE = rawBase.replace(/\/+$/, '');

// WebSocket base — derive from API_BASE (http→ws, https→wss)
export const WS_BASE = API_BASE.replace(/^http/, 'ws');
