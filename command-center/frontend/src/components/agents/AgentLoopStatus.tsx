'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchLoopStatus, startAgentLoop, stopAgentLoop } from '@/lib/agents-api';
import type { LoopStatus } from '@/lib/agents-api';

interface Props {
  agentId: string;
}

export default function AgentLoopStatus({ agentId }: Props) {
  const [status, setStatus] = useState<LoopStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchLoopStatus(agentId);
      setStatus(data);
    } catch (err) {
      console.error('Loop status error:', err);
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => { load(); }, [load]);

  async function handleToggle() {
    if (!status) return;
    setActionLoading(true);
    try {
      if (status.running) {
        await stopAgentLoop(agentId);
      } else {
        await startAgentLoop(agentId);
      }
      await load();
    } catch (err) {
      console.error('Loop toggle error:', err);
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="text-sm text-zinc-500 animate-pulse p-4">Loading loop status...</div>;
  if (!status) return <div className="text-sm text-zinc-500 p-4">Unable to load loop status</div>;

  return (
    <div className="p-4 space-y-4">
      {/* Status card */}
      <div className="flex items-center justify-between bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${status.running ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
          <div>
            <div className="text-sm font-medium text-zinc-200">{status.running ? 'Running' : 'Stopped'}</div>
            <div className="text-xs text-zinc-400">
              {status.iteration_count} iterations
              {status.started_at && ` &middot; since ${new Date(status.started_at).toLocaleTimeString()}`}
            </div>
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={actionLoading}
          className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
            status.running
              ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30'
              : 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30'
          } disabled:opacity-50`}
        >
          {actionLoading ? '...' : status.running ? 'Stop' : 'Start'}
        </button>
      </div>

      {/* Last action */}
      {status.last_action && (
        <div className="bg-zinc-800/30 rounded-lg p-3 border border-zinc-700/30">
          <div className="text-xs text-zinc-400 mb-1">Last Action</div>
          <div className="text-sm text-zinc-200">{status.last_action}</div>
        </div>
      )}

      {/* Last error */}
      {status.last_error && (
        <div className="bg-red-900/20 rounded-lg p-3 border border-red-500/20">
          <div className="text-xs text-red-400 mb-1">Last Error</div>
          <div className="text-sm text-zinc-200">{status.last_error}</div>
        </div>
      )}
    </div>
  );
}
