'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useStore } from '../lib/store';
import type { BrainMessage } from '../lib/store';

/**
 * BrainSidebar — Persistent right sidebar for AI Brain interaction.
 *
 * Features:
 *   - Collapsible panel (toggle button always visible)
 *   - Brain status indicator (online/offline with provider info)
 *   - Chat message history (user questions + brain responses + auto-insights)
 *   - Chat input with Enter-to-send
 *   - "Analyze Now" button for on-demand system analysis
 *   - Auto-scroll to latest message
 *   - Token input for authentication (reads from sessionStorage)
 */
export default function BrainSidebar() {
  const {
    brainMessages,
    brainSidebarOpen,
    brainLoading,
    brainStatus,
    toggleBrainSidebar,
    addBrainMessage,
    setBrainLoading,
    setBrainStatus,
  } = useStore();

  const [input, setInput] = useState('');
  const [token, setToken] = useState('');
  const [showTokenInput, setShowTokenInput] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ------------------------------------------------------------------
  // Token management
  // ------------------------------------------------------------------

  useEffect(() => {
    // Token priority: localStorage (shared with main app) > URL param > auto-fetch
    const stored = localStorage.getItem('cc-token');
    if (stored) {
      setToken(stored);
    } else {
      // Check URL params (dev convenience)
      const params = new URLSearchParams(window.location.search);
      const urlToken = params.get('token');
      if (urlToken) {
        setToken(urlToken);
        localStorage.setItem('cc-token', urlToken);
      } else {
        // Auto-fetch token from backend (same as useWebSocket resolveToken)
        fetch('/api/settings/token')
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data?.token) {
              setToken(data.token);
              localStorage.setItem('cc-token', data.token);
            }
          })
          .catch(() => {});
      }
    }

    // Listen for token changes from main app (e.g., useWebSocket resolved it)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'cc-token' && e.newValue) {
        setToken(e.newValue);
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  function saveToken(newToken: string) {
    setToken(newToken);
    localStorage.setItem('cc-token', newToken);
    // Also clear old sessionStorage key (migration from old behavior)
    sessionStorage.removeItem('cc-auth-token');
    setShowTokenInput(false);
    fetchBrainStatus(newToken);
  }

  function getAuthHeaders(overrideToken?: string): Record<string, string> {
    const t = overrideToken || token;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (t) {
      headers['Authorization'] = `Bearer ${t}`;
    }
    return headers;
  }

  // ------------------------------------------------------------------
  // Brain status
  // ------------------------------------------------------------------

  const fetchBrainStatus = useCallback(async (overrideToken?: string) => {
    try {
      const res = await fetch('/api/brain/status', {
        headers: getAuthHeaders(overrideToken),
      });
      if (res.ok) {
        const data = await res.json();
        setBrainStatus(data);
      }
    } catch (e) {
      console.error('Failed to fetch brain status:', e);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchBrainStatus();
    }
  }, [token, fetchBrainStatus]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [brainMessages]);

  // Focus input when sidebar opens
  useEffect(() => {
    if (brainSidebarOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [brainSidebarOpen]);

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  async function handleSend() {
    if (!input.trim() || brainLoading) return;

    const question = input.trim();
    setInput('');

    addBrainMessage({
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
      type: 'question',
    });

    setBrainLoading(true);

    try {
      const res = await fetch('/api/brain/ask', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ question }),
      });

      if (res.ok) {
        const data = await res.json();
        addBrainMessage({
          role: 'assistant',
          content: data.content,
          timestamp: data.timestamp,
          type: data.type || 'response',
        });
      } else if (res.status === 401 || res.status === 403) {
        setShowTokenInput(true);
        addBrainMessage({
          role: 'system',
          content: 'Authentication required. Enter your token above.',
          timestamp: new Date().toISOString(),
          type: 'error',
        });
      } else {
        const errText = await res.text();
        addBrainMessage({
          role: 'assistant',
          content: `Error (${res.status}): ${errText}`,
          timestamp: new Date().toISOString(),
          type: 'error',
        });
      }
    } catch (e: any) {
      addBrainMessage({
        role: 'assistant',
        content: `Connection error: ${e?.message || e}`,
        timestamp: new Date().toISOString(),
        type: 'error',
      });
    } finally {
      setBrainLoading(false);
    }
  }

  async function handleAnalyze() {
    setBrainLoading(true);
    try {
      const res = await fetch('/api/brain/analyze', {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        addBrainMessage({
          role: 'assistant',
          content: data.content,
          timestamp: data.timestamp,
          type: 'insight',
        });
      } else if (res.status === 401 || res.status === 403) {
        setShowTokenInput(true);
      }
    } catch (e) {
      console.error('Analysis failed:', e);
    } finally {
      setBrainLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // ------------------------------------------------------------------
  // Render helpers
  // ------------------------------------------------------------------

  function renderMessage(msg: BrainMessage, i: number) {
    const isUser = msg.role === 'user';
    const isInsight = msg.type === 'insight';
    const isError = msg.type === 'error';

    let bgClass = 'bg-nc-surface-2 text-nc-text';
    if (isUser) bgClass = 'bg-nc-accent text-white';
    else if (isError) bgClass = 'bg-nc-red/10 text-nc-red border border-nc-red/20';
    else if (isInsight) bgClass = 'bg-nc-yellow/10 text-nc-text border border-nc-yellow/20';

    return (
      <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className={`max-w-[92%] rounded-lg px-3 py-2 text-[13px] leading-relaxed ${bgClass}`}>
          {isInsight && (
            <div className="text-[11px] font-semibold text-nc-yellow mb-1 flex items-center gap-1">
              <span>✦</span> Strategic Insight
            </div>
          )}
          <div className="whitespace-pre-wrap break-words">{msg.content}</div>
          <div
            className={`text-[10px] mt-1 ${
              isUser ? 'text-indigo-200' : 'text-nc-text-muted'
            }`}
          >
            {new Date(msg.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        </div>
      </div>
    );
  }

  // ------------------------------------------------------------------
  // Toggle button (always visible on right edge)
  // ------------------------------------------------------------------

  const toggleBtn = (
    <button
      onClick={toggleBrainSidebar}
      className="fixed right-0 top-1/2 -translate-y-1/2 z-50 flex items-center justify-center w-8 h-14 glass-bright text-nc-accent hover:text-white rounded-l-lg shadow-lg transition-all duration-200"
      title={brainSidebarOpen ? 'Close AI Brain' : 'Open AI Brain'}
      style={{ right: brainSidebarOpen ? '320px' : '0px' }}
    >
      <span className="text-sm">{brainSidebarOpen ? '›' : '🧠'}</span>
    </button>
  );

  if (!brainSidebarOpen) return toggleBtn;

  // ------------------------------------------------------------------
  // Full sidebar
  // ------------------------------------------------------------------

  return (
    <>
      {toggleBtn}
      <div className="w-80 h-full border-l border-nc-border bg-nc-surface flex flex-col flex-shrink-0">
        {/* ---- Header ---- */}
        <div className="px-3 py-2.5 border-b border-nc-border bg-nc-surface-2/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">🧠</span>
              <span className="font-semibold text-nc-text text-sm">AI Brain</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                className={`w-2 h-2 rounded-full ${
                  brainStatus?.available ? 'bg-nc-green' : 'bg-nc-text-muted'
                }`}
              />
              <span className="text-[11px] text-nc-text-dim">
                {brainStatus?.available
                  ? brainStatus.provider
                  : 'offline'}
              </span>
            </div>
          </div>

          {/* Token input (shown when auth fails) */}
          {showTokenInput && (
            <div className="mt-2">
              <input
                type="text"
                placeholder="Paste auth token from backend log"
                className="w-full text-xs bg-nc-bg border border-nc-border-bright rounded px-2 py-1.5 text-nc-text focus:outline-none focus:border-nc-accent"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    saveToken((e.target as HTMLInputElement).value.trim());
                  }
                }}
              />
              <p className="text-[10px] text-nc-text-muted mt-0.5">
                Press Enter to save. Token is in backend startup log.
              </p>
            </div>
          )}

          {/* Analyze button */}
          {brainStatus?.available && (
            <button
              onClick={handleAnalyze}
              disabled={brainLoading}
              className="mt-2 w-full text-xs bg-nc-accent/10 hover:bg-nc-accent/20 text-nc-accent px-3 py-1.5 rounded transition-colors disabled:opacity-50 font-medium"
            >
              {brainLoading ? '⏳ Analyzing...' : '✦ Analyze System Now'}
            </button>
          )}
        </div>

        {/* ---- Messages ---- */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2.5 scroll-smooth">
          {brainMessages.length === 0 && (
            <div className="text-center text-nc-text-muted text-xs mt-12 px-4 leading-relaxed">
              {brainStatus?.available ? (
                <>
                  <p className="mb-2">Ask a question about your system</p>
                  <p className="text-nc-text-dim">
                    Try: &ldquo;What should I prioritize next?&rdquo;
                  </p>
                </>
              ) : !token ? (
                <>
                  <p className="mb-2">Enter your auth token to connect</p>
                  <button
                    onClick={() => setShowTokenInput(true)}
                    className="text-nc-accent hover:text-nc-accent-dim underline text-xs"
                  >
                    Enter token
                  </button>
                </>
              ) : (
                <p>
                  Configure an API key in <code className="bg-nc-surface-2 px-1 rounded text-nc-text-dim">config/.env</code> and restart
                  the backend to enable the AI Brain.
                </p>
              )}
            </div>
          )}

          {brainMessages.map((msg, i) => renderMessage(msg, i))}

          {brainLoading && (
            <div className="flex justify-start">
              <div className="bg-nc-surface-2 rounded-lg px-3 py-2 text-sm text-nc-text-dim">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: '0ms' }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>·</span>
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ---- Input ---- */}
        <div className="px-3 py-2.5 border-t border-nc-border bg-nc-surface">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                brainStatus?.available
                  ? 'Ask about your system...'
                  : 'Brain offline'
              }
              disabled={!brainStatus?.available || brainLoading}
              className="flex-1 text-sm bg-nc-bg border border-nc-border-bright rounded-lg px-3 py-2 text-nc-text placeholder:text-nc-text-muted focus:outline-none focus:ring-1 focus:ring-nc-accent focus:border-nc-accent disabled:bg-nc-surface-2 disabled:text-nc-text-muted transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || brainLoading || !brainStatus?.available}
              className="bg-nc-accent hover:bg-nc-accent-dim text-white w-9 h-9 rounded-lg text-sm disabled:opacity-40 transition-colors flex items-center justify-center flex-shrink-0"
            >
              ↑
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
