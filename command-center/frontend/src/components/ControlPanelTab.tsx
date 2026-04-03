'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchEngineStatus,
  fetchExecutionStatus,
  fetchExecutionQueue,
  fetchBudget,
  fetchBridges,
  fetchSettings,
  startAllAgents,
  stopAllAgents,
  setExecutionMode,
  refreshState,
} from '@/lib/engine-api';
import type { EngineState } from '@/lib/engine-api';
import { fetchAgentProfiles, startAgentLoop, stopAgentLoop } from '@/lib/agents-api';
import type { AgentProfile } from '@/lib/agents-api';
import type { ProviderBudget } from '@/lib/types';

const AUTHORITY_LABELS: Record<number, string> = { 1: 'L1', 2: 'L2', 3: 'L3' };

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function BudgetBar({ provider }: { provider: ProviderBudget }) {
  const pct = Math.min(provider.percent_used, 100);
  const color = pct > 80 ? 'bg-nc-red' : pct > 50 ? 'bg-nc-yellow' : 'bg-nc-green';
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-nc-text w-24 font-medium capitalize">{provider.provider}</span>
      <div className="flex-1 bg-nc-surface-2 rounded-full h-3 overflow-hidden">
        <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-nc-text-dim w-28 text-right">
        ${provider.spent.toFixed(2)} / ${provider.limit.toFixed(0)} ({Math.round(pct)}%)
      </span>
    </div>
  );
}

interface AgentLoopInfo {
  agent_id: string;
  running: boolean;
  tasks_completed?: number;
  cost?: number;
}

export default function ControlPanelTab() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loopStates, setLoopStates] = useState<Record<string, AgentLoopInfo>>({});
  const [engineState, setEngineState] = useState<EngineState | null>(null);
  const [queueStats, setQueueStats] = useState<{ total_queued: number; total_active: number } | null>(null);
  const [budget, setBudget] = useState<ProviderBudget[]>([]);
  const [bridges, setBridges] = useState<Record<string, { status: string; enabled: boolean }>>({});
  const [settings, setSettings] = useState<any>(null);
  const [activeMode, setActiveMode] = useState('balanced');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [agentsData, engineData, execStatus, queueData, budgetData, bridgesData, settingsData] =
        await Promise.all([
          fetchAgentProfiles(),
          fetchEngineStatus().catch(() => ({ loops: {} })),
          fetchExecutionStatus().catch(() => null),
          fetchExecutionQueue().catch(() => ({ total_queued: 0, total_active: 0 })),
          fetchBudget().catch(() => ({ providers: [] })),
          fetchBridges().catch(() => ({ bridges: {} })),
          fetchSettings().catch(() => null),
        ]);

      setAgents(agentsData.agents);

      // Build loop state map from engine status
      const loops: Record<string, AgentLoopInfo> = {};
      if (engineData.loops) {
        for (const [id, info] of Object.entries(engineData.loops as Record<string, any>)) {
          loops[id] = {
            agent_id: id,
            running: info.running ?? false,
            tasks_completed: info.iteration_count ?? 0,
            cost: info.cost ?? 0,
          };
        }
      }
      setLoopStates(loops);

      if (execStatus) {
        setEngineState(execStatus);
        setActiveMode(execStatus.mode || 'balanced');
      }
      setQueueStats(queueData);
      setBudget(budgetData.providers || []);
      setBridges(bridgesData.bridges || {});
      setSettings(settingsData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load control data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleStartAll = useCallback(async () => {
    setActionLoading('start-all');
    try { await startAllAgents(); await loadAll(); } catch (e: any) { setError(e.message); }
    setActionLoading(null);
  }, [loadAll]);

  const handleStopAll = useCallback(async () => {
    setActionLoading('stop-all');
    try { await stopAllAgents(); await loadAll(); } catch (e: any) { setError(e.message); }
    setActionLoading(null);
  }, [loadAll]);

  const handleToggleAgent = useCallback(async (agentId: string, running: boolean) => {
    setActionLoading(agentId);
    try {
      if (running) await stopAgentLoop(agentId);
      else await startAgentLoop(agentId);
      await loadAll();
    } catch (e: any) { setError(e.message); }
    setActionLoading(null);
  }, [loadAll]);

  const handleSetMode = useCallback(async (mode: string) => {
    setActionLoading('mode');
    try {
      await setExecutionMode(mode);
      setActiveMode(mode);
    } catch (e: any) { setError(e.message); }
    setActionLoading(null);
  }, []);

  const handleRefresh = useCallback(async () => {
    setActionLoading('refresh');
    try { await refreshState(); await loadAll(); } catch (e: any) { setError(e.message); }
    setActionLoading(null);
  }, [loadAll]);

  if (loading) return <div className="flex items-center justify-center h-full text-nc-text-dim text-sm">Loading control panel...</div>;

  const runningCount = Object.values(loopStates).filter(l => l.running).length;

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* System Status Bar */}
        <div className="bg-nc-surface border border-nc-border rounded-xl px-5 py-3 flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-nc-green" />
            <span className="text-sm font-semibold text-nc-text">System Online</span>
          </div>
          <span className="text-sm text-nc-text-dim">Agents: {runningCount}/{agents.length}</span>
          {engineState && (
            <>
              <span className="text-sm text-nc-text-dim">Uptime: {formatUptime(engineState.uptime_seconds)}</span>
              <span className="text-sm text-nc-text-dim">Completed: {engineState.completed_today}</span>
              <span className="text-sm text-nc-text-dim">Failed: {engineState.failed_today}</span>
            </>
          )}
        </div>

        {error && (
          <div className="p-3 bg-nc-red/10 border border-nc-red/20 rounded-lg text-sm text-nc-red flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="font-bold hover:opacity-70">&times;</button>
          </div>
        )}

        {/* Agent Controls */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider">Agent Controls</h2>
            <div className="flex gap-2">
              <button onClick={handleStartAll} disabled={actionLoading === 'start-all'}
                className="px-3 py-1.5 bg-nc-green/10 text-nc-green border border-nc-green/20 rounded-lg text-xs font-medium hover:bg-nc-green/20 transition-colors disabled:opacity-50">
                Start All
              </button>
              <button onClick={handleStopAll} disabled={actionLoading === 'stop-all'}
                className="px-3 py-1.5 bg-nc-red/10 text-nc-red border border-nc-red/20 rounded-lg text-xs font-medium hover:bg-nc-red/20 transition-colors disabled:opacity-50">
                Stop All
              </button>
              <button onClick={handleStopAll} disabled={actionLoading === 'stop-all'}
                className="px-3 py-1.5 bg-nc-red text-white rounded-lg text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
                Emergency Stop
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {agents.map((agent) => {
              const loop = loopStates[agent.id];
              const running = loop?.running ?? false;
              return (
                <div key={agent.id} className="bg-nc-surface border border-nc-border rounded-xl p-4 flex items-center gap-3">
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${running ? 'bg-nc-green' : 'bg-nc-text-dim/30'}`} />
                  <span className="text-lg flex-shrink-0">{agent.avatar}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-nc-text truncate">{agent.character_name || agent.name}</span>
                      <span className="text-[10px] text-nc-text-dim font-medium">{AUTHORITY_LABELS[agent.authority_level] || `L${agent.authority_level}`}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-nc-text-dim mt-0.5">
                      <span>{running ? 'Running' : 'Stopped'}</span>
                      {loop?.tasks_completed != null && <span>tasks: {loop.tasks_completed}</span>}
                      {loop?.cost != null && loop.cost > 0 && <span>${loop.cost.toFixed(2)}</span>}
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleAgent(agent.id, running)}
                    disabled={actionLoading === agent.id}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors flex-shrink-0 disabled:opacity-50 ${
                      running
                        ? 'bg-nc-red/10 text-nc-red border border-nc-red/20 hover:bg-nc-red/20'
                        : 'bg-nc-green/10 text-nc-green border border-nc-green/20 hover:bg-nc-green/20'
                    }`}
                  >
                    {actionLoading === agent.id ? '...' : running ? 'Stop' : 'Start'}
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        {/* Execution Engine */}
        <section>
          <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">Execution Engine</h2>
          <div className="bg-nc-surface border border-nc-border rounded-xl p-5 space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-nc-text-dim">Mode:</span>
              {['conservative', 'balanced', 'aggressive'].map((mode) => (
                <button key={mode} onClick={() => handleSetMode(mode)}
                  disabled={actionLoading === 'mode'}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${
                    activeMode === mode
                      ? 'bg-nc-accent text-white'
                      : 'bg-nc-surface-2 text-nc-text-dim border border-nc-border hover:text-nc-text'
                  }`}>
                  {mode}{activeMode === mode ? ' \u25CF' : ''}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-6 text-sm">
              <span className="text-nc-text-dim">Queue: <span className="text-nc-text font-medium">{queueStats?.total_queued ?? 0} pending</span></span>
              <span className="text-nc-text-dim">Active: <span className="text-nc-text font-medium">{queueStats?.total_active ?? 0} running</span></span>
              {engineState && (
                <>
                  <span className="text-nc-text-dim">Completed: <span className="text-nc-text font-medium">{engineState.completed_today}</span></span>
                  <span className="text-nc-text-dim">Dead Letter: <span className="text-nc-text font-medium">{engineState.dead_letter_count}</span></span>
                </>
              )}
            </div>
          </div>
        </section>

        {/* Quick Actions */}
        <section>
          <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">Quick Actions</h2>
          <div className="flex flex-wrap gap-2">
            <button onClick={handleRefresh} disabled={actionLoading === 'refresh'}
              className="px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
              {actionLoading === 'refresh' ? 'Refreshing...' : 'Force State Refresh'}
            </button>
            <button onClick={loadAll}
              className="px-4 py-2 bg-nc-surface-2 text-nc-text border border-nc-border rounded-lg text-sm font-medium hover:bg-nc-surface transition-colors">
              Reload Dashboard
            </button>
          </div>
        </section>

        {/* Budget & Providers */}
        <section>
          <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">Budget &amp; Providers</h2>
          <div className="bg-nc-surface border border-nc-border rounded-xl p-5 space-y-3">
            {budget.length === 0 ? (
              <span className="text-sm text-nc-text-dim">No budget data available</span>
            ) : (
              budget.map((p) => <BudgetBar key={p.provider} provider={p} />)
            )}
          </div>
        </section>

        {/* Tool Health */}
        <section>
          <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">Tool Health</h2>
          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {Object.entries(bridges).length === 0 ? (
                <span className="text-sm text-nc-text-dim col-span-full">No bridge data available</span>
              ) : (
                Object.entries(bridges).map(([name, info]) => {
                  const status = typeof info === 'object' ? info.status : info;
                  const isHealthy = status === 'connected' || status === 'healthy';
                  return (
                    <div key={name} className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isHealthy ? 'bg-nc-green' : status === 'mocked' ? 'bg-nc-yellow' : 'bg-nc-red'}`} />
                      <span className="text-sm text-nc-text capitalize">{name.replace(/_/g, ' ')}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </section>

        {/* System Config */}
        <section>
          <h2 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">System Config</h2>
          <div className="bg-nc-surface border border-nc-border rounded-xl p-5 space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-nc-text-dim w-44">Execution mode:</span>
              <span className="text-nc-text font-medium capitalize">{activeMode}</span>
            </div>
            {settings?.intervals?.brain && (
              <div className="flex items-center gap-2">
                <span className="text-nc-text-dim w-44">Auto-insight interval:</span>
                <span className="text-nc-text font-medium">{settings.intervals.brain}s</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-nc-text-dim w-44">Default LLM:</span>
              <span className="text-nc-text font-medium">claude-sonnet-4-6</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-nc-text-dim w-44">Brain status:</span>
              <span className="text-nc-text font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-nc-green" />
                Online
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
