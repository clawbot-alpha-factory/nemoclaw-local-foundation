'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchActivity,
  fetchActivityStats,
  fetchDecisionLog,
  fetchAuditLog,
} from '../lib/intelligence-api';
import type {
  ActivityEntry,
  ActivityCategory,
  ActivityStats,
  DecisionEntry,
  AuditEntry,
} from '../lib/intelligence-api';

type SubView = 'timeline' | 'decisions' | 'health' | 'audit';

const SUB_VIEWS: { id: SubView; label: string }[] = [
  { id: 'timeline', label: 'Activity Timeline' },
  { id: 'decisions', label: 'Decision Log' },
  { id: 'health', label: 'System Health' },
  { id: 'audit', label: 'Audit Trail' },
];

const CATEGORIES: ActivityCategory[] = ['execution', 'protocol', 'bridge', 'lifecycle', 'system', 'memory'];

const CATEGORY_COLORS: Record<string, string> = {
  execution: 'bg-blue-500/20 text-blue-400',
  protocol: 'bg-purple-500/20 text-purple-400',
  bridge: 'bg-emerald-500/20 text-emerald-400',
  lifecycle: 'bg-amber-500/20 text-amber-400',
  system: 'bg-slate-500/20 text-slate-400',
  memory: 'bg-pink-500/20 text-pink-400',
};

function Badge({ label, className }: { label: string; className?: string }) {
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${className || 'bg-nc-surface-2 text-nc-text-dim'}`}>
      {label}
    </span>
  );
}

// ─── Activity Timeline ───────────────────────────────────────────────────────

function TimelineView() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [stats, setStats] = useState<ActivityStats | null>(null);
  const [filter, setFilter] = useState<ActivityCategory | ''>('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [actData, statsData] = await Promise.all([
        fetchActivity({ category: filter || undefined, limit: 100 }),
        fetchActivityStats(),
      ]);
      setEntries(actData.entries);
      setStats(statsData);
    } catch (err) {
      console.error('Activity load error:', err);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-6 gap-3">
          {CATEGORIES.map((cat) => (
            <div key={cat} className="bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
              <div className="text-lg font-bold text-nc-text">{stats.by_category[cat] || 0}</div>
              <div className="text-[10px] text-nc-text-dim capitalize">{cat}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter chips */}
      <div className="flex gap-1">
        <button
          onClick={() => setFilter('')}
          className={`px-2 py-1 text-xs rounded-lg transition-colors ${
            !filter ? 'bg-nc-accent/20 text-nc-accent' : 'text-nc-text-dim hover:bg-nc-surface-2'
          }`}
        >All</button>
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-2 py-1 text-xs rounded-lg transition-colors capitalize ${
              filter === cat ? 'bg-nc-accent/20 text-nc-accent' : 'text-nc-text-dim hover:bg-nc-surface-2'
            }`}
          >{cat}</button>
        ))}
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="text-center py-8 text-sm text-nc-text-dim animate-pulse">Loading...</div>
      ) : (
        <div className="space-y-1">
          {entries.map((e) => (
            <div key={e.id} className="flex items-start gap-3 px-3 py-2 rounded-lg hover:bg-nc-surface-2 transition-colors">
              <div className="text-[10px] text-nc-text-dim w-16 shrink-0 pt-0.5">
                {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
              <Badge label={e.category} className={CATEGORY_COLORS[e.category]} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-nc-text">{e.summary}</div>
                <div className="text-[10px] text-nc-text-dim">
                  {e.actor_id} &middot; {e.entity_type}/{e.entity_id} &middot; {e.action}
                </div>
              </div>
            </div>
          ))}
          {entries.length === 0 && (
            <div className="text-center py-8 text-sm text-nc-text-dim">No activity entries</div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Decision Log ────────────────────────────────────────────────────────────

function DecisionLogView() {
  const [decisions, setDecisions] = useState<DecisionEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDecisionLog(100)
      .then(({ decisions: d }) => setDecisions(Array.isArray(d) ? d : []))
      .catch(() => setDecisions([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-8 text-sm text-nc-text-dim animate-pulse">Loading...</div>;

  return (
    <div className="space-y-2">
      {decisions.map((d) => (
        <div key={d.id} className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <div className="flex items-start justify-between mb-2">
            <div className="text-sm font-medium text-nc-text">{d.decision}</div>
            <span className="text-[10px] text-nc-text-dim shrink-0 ml-3">
              {new Date(d.timestamp).toLocaleString()}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-nc-text-dim">Action: </span>
              <span className="text-nc-text">{d.action_taken}</span>
            </div>
            <div>
              <span className="text-nc-text-dim">Result: </span>
              <span className="text-nc-text">{d.result}</span>
            </div>
          </div>
          {d.agent_id && (
            <div className="text-[10px] text-nc-text-dim mt-2">Agent: {d.agent_id}</div>
          )}
        </div>
      ))}
      {decisions.length === 0 && (
        <div className="text-center py-8 text-sm text-nc-text-dim">No decisions recorded</div>
      )}
    </div>
  );
}

// ─── System Health ───────────────────────────────────────────────────────────

function SystemHealthView({ systemState }: { systemState: any }) {
  const health = systemState?.health;
  const validation = systemState?.validation;

  const statusColor = (s: string) =>
    s === 'healthy' ? 'bg-nc-green' :
    s === 'warning' ? 'bg-nc-yellow' :
    s === 'error' ? 'bg-nc-red' :
    'bg-gray-500';

  return (
    <div className="space-y-6">
      {/* Overall status */}
      <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${statusColor(health?.overall || 'unknown')}`} />
          <span className="text-lg font-semibold text-nc-text capitalize">{health?.overall || 'Unknown'}</span>
        </div>
      </div>

      {/* Domain grid */}
      <div className="grid grid-cols-3 gap-3">
        {(health?.domains || []).map((d: any) => (
          <div key={d.domain} className="bg-nc-surface rounded-lg border border-nc-border p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className={`w-2 h-2 rounded-full ${statusColor(d.status)}`} />
              <span className="text-sm font-medium text-nc-text capitalize">{d.domain}</span>
            </div>
            <div className="text-xs text-nc-text-dim">{d.message}</div>
            {d.last_check && (
              <div className="text-[10px] text-nc-text-dim mt-1">
                Checked: {new Date(d.last_check).toLocaleTimeString()}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Validation */}
      {validation && (
        <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <h3 className="text-sm font-medium text-nc-text mb-3">Validation ({validation.total_checks} checks)</h3>
          <div className="flex gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-nc-green">{validation.passed}</div>
              <div className="text-[10px] text-nc-text-dim">Passed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-nc-yellow">{validation.warnings}</div>
              <div className="text-[10px] text-nc-text-dim">Warnings</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-nc-red">{validation.failed}</div>
              <div className="text-[10px] text-nc-text-dim">Failed</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Audit Trail ─────────────────────────────────────────────────────────────

function AuditTrailView() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuditLog(100)
      .then(({ entries: e }) => setEntries(Array.isArray(e) ? e : []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-8 text-sm text-nc-text-dim animate-pulse">Loading...</div>;

  return (
    <div className="bg-nc-surface rounded-lg border border-nc-border overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-nc-border">
            <th className="text-left p-2 text-nc-text-dim font-medium">Time</th>
            <th className="text-left p-2 text-nc-text-dim font-medium">Action</th>
            <th className="text-left p-2 text-nc-text-dim font-medium">Actor</th>
            <th className="text-left p-2 text-nc-text-dim font-medium">Entity</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="border-b border-nc-border/30 hover:bg-nc-surface-2">
              <td className="p-2 text-nc-text-dim">{new Date(e.timestamp).toLocaleString()}</td>
              <td className="p-2 text-nc-text">{e.action}</td>
              <td className="p-2 text-nc-text-dim">{e.actor}</td>
              <td className="p-2 text-nc-text-dim">{e.entity_type}/{e.entity_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {entries.length === 0 && (
        <div className="text-center py-8 text-sm text-nc-text-dim">No audit entries</div>
      )}
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function IntelligenceTab() {
  const [view, setView] = useState<SubView>('timeline');

  // For system health, we read from the WebSocket state
  const [systemState, setSystemState] = useState<any>(null);

  useEffect(() => {
    // Fetch current state for health view
    const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
    fetch('http://127.0.0.1:8100/api/state', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.json())
      .then(setSystemState)
      .catch(console.error);
  }, []);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-nc-border">
        <h1 className="text-lg font-semibold text-nc-text">Intelligence</h1>
        <p className="text-xs text-nc-text-dim">Activity timeline, decisions, system health, audit trail</p>
      </div>

      {/* Sub-nav */}
      <div className="px-6 py-2 border-b border-nc-border flex gap-1">
        {SUB_VIEWS.map((sv) => (
          <button
            key={sv.id}
            onClick={() => setView(sv.id)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              view === sv.id
                ? 'bg-nc-accent/20 text-nc-accent'
                : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
            }`}
          >{sv.label}</button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {view === 'timeline' && <TimelineView />}
        {view === 'decisions' && <DecisionLogView />}
        {view === 'health' && <SystemHealthView systemState={systemState} />}
        {view === 'audit' && <AuditTrailView />}
      </div>
    </div>
  );
}
