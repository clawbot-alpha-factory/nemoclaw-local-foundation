'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchBudgetOverview,
  fetchBudgetByAgent,
  fetchBudgetBySkill,
  fetchCircuitBreakers,
  fetchUsageLog,
} from '../lib/finance-api';
import type {
  BudgetOverview,
  AgentCostBreakdown,
  SkillCostBreakdown,
  CircuitBreakerStatus,
  UsageLogEntry,
  UsageLogResponse,
} from '../lib/finance-types';

type SubView = 'overview' | 'providers' | 'agents' | 'skills' | 'log';

const SUB_VIEWS: { id: SubView; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'providers', label: 'By Provider' },
  { id: 'agents', label: 'By Agent' },
  { id: 'skills', label: 'By Skill' },
  { id: 'log', label: 'Usage Log' },
];

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'CLOSED' ? 'bg-nc-green' :
    status === 'OPEN' ? 'bg-nc-red' :
    'bg-nc-yellow';
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}

function ProgressBar({ percent, warn }: { percent: number; warn?: boolean }) {
  const color =
    percent >= 100 ? 'bg-nc-red' :
    percent >= 90 || warn ? 'bg-nc-yellow' :
    'bg-nc-accent';
  return (
    <div className="w-full h-2 bg-nc-surface-2 rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  );
}

// ─── Overview ────────────────────────────────────────────────────────────────

function OverviewView({ data }: { data: BudgetOverview | null }) {
  if (!data) return <LoadingState />;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard label="Total Spent" value={`$${data.total_spent.toFixed(2)}`} sub={`of $${data.total_limit.toFixed(0)} budget`} />
        <SummaryCard label="Burn Rate" value={`$${data.burn_rate_per_hour.toFixed(4)}/hr`} sub="current rate" />
        <SummaryCard label="Budget Used" value={`${((data.total_spent / data.total_limit) * 100).toFixed(1)}%`}
          sub={data.total_spent / data.total_limit > 0.9 ? 'WARNING' : 'healthy'} />
        <SummaryCard label="Projected Exhaustion"
          value={data.projected_exhaustion ? new Date(data.projected_exhaustion).toLocaleDateString() : 'N/A'}
          sub={data.projected_exhaustion ? 'estimated' : 'within budget'} />
      </div>

      {/* Provider bars */}
      <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
        <h3 className="text-sm font-medium text-nc-text mb-4">Provider Budget</h3>
        <div className="space-y-4">
          {data.providers.map((p) => (
            <div key={p.provider}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-nc-text">{p.provider}</span>
                <span className="text-nc-text-dim">${p.spent.toFixed(2)} / ${p.limit.toFixed(0)}</span>
              </div>
              <ProgressBar percent={p.percent_used} warn={p.percent_used >= p.warn_threshold} />
            </div>
          ))}
        </div>
      </div>

      {/* Circuit breakers */}
      <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
        <h3 className="text-sm font-medium text-nc-text mb-4">Circuit Breakers</h3>
        <div className="grid grid-cols-3 gap-4">
          {data.circuit_breakers.map((cb) => (
            <div key={cb.provider} className="bg-nc-surface-2 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <StatusDot status={cb.state} />
                <span className="text-sm font-medium text-nc-text">{cb.provider}</span>
              </div>
              <div className="text-xs text-nc-text-dim">
                State: <span className="text-nc-text">{cb.state}</span>
              </div>
              <div className="text-xs text-nc-text-dim">
                Ratio: <span className="text-nc-text">{(cb.current_ratio * 100).toFixed(0)}%</span> of {(cb.trip_threshold * 100).toFixed(0)}% trip
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Providers ───────────────────────────────────────────────────────────────

function ProvidersView({ data }: { data: BudgetOverview | null }) {
  if (!data) return <LoadingState />;

  return (
    <div className="grid grid-cols-3 gap-6">
      {data.providers.map((p) => (
        <div key={p.provider} className="bg-nc-surface rounded-lg border border-nc-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-nc-text">{p.provider}</h3>
            <StatusDot status={data.circuit_breakers.find(cb => cb.provider === p.provider)?.state || 'CLOSED'} />
          </div>
          <div className="text-2xl font-bold text-nc-text mb-1">${p.spent.toFixed(2)}</div>
          <div className="text-xs text-nc-text-dim mb-3">of ${p.limit.toFixed(0)} limit</div>
          <ProgressBar percent={p.percent_used} />
          <div className="mt-3 text-xs text-nc-text-dim">
            {p.percent_used.toFixed(1)}% used
            {p.percent_used >= 90 && <span className="text-nc-yellow ml-2">Approaching limit</span>}
            {p.percent_used >= 100 && <span className="text-nc-red ml-2">HARD STOP</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── By Agent ────────────────────────────────────────────────────────────────

function AgentCostView({ agents }: { agents: AgentCostBreakdown[] | null }) {
  if (!agents) return <LoadingState />;

  const sorted = [...agents].sort((a, b) => b.total_spent - a.total_spent);
  const maxSpent = sorted[0]?.total_spent || 1;

  return (
    <div className="bg-nc-surface rounded-lg border border-nc-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-nc-border">
            <th className="text-left p-3 text-nc-text-dim font-medium">Agent</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Total Spent</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Calls</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Avg/Call</th>
            <th className="p-3 text-nc-text-dim font-medium w-48">Distribution</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr key={a.agent_id} className="border-b border-nc-border/50 hover:bg-nc-surface-2">
              <td className="p-3">
                <div className="text-nc-text font-medium">{a.agent_name}</div>
                <div className="text-xs text-nc-text-dim">{a.agent_id}</div>
              </td>
              <td className="p-3 text-right text-nc-text">${a.total_spent.toFixed(4)}</td>
              <td className="p-3 text-right text-nc-text-dim">{a.call_count}</td>
              <td className="p-3 text-right text-nc-text-dim">${a.avg_cost_per_call.toFixed(6)}</td>
              <td className="p-3">
                <div className="w-full h-2 bg-nc-surface-2 rounded-full overflow-hidden">
                  <div className="h-full bg-nc-accent rounded-full" style={{ width: `${(a.total_spent / maxSpent) * 100}%` }} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── By Skill ────────────────────────────────────────────────────────────────

function SkillCostView({ skills }: { skills: SkillCostBreakdown[] | null }) {
  if (!skills) return <LoadingState />;

  const sorted = [...skills].sort((a, b) => b.total_spent - a.total_spent);

  return (
    <div className="bg-nc-surface rounded-lg border border-nc-border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-nc-border">
            <th className="text-left p-3 text-nc-text-dim font-medium">Skill</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Total Cost</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Runs</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Avg/Run</th>
            <th className="text-right p-3 text-nc-text-dim font-medium">Last Run</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr key={s.skill_id} className="border-b border-nc-border/50 hover:bg-nc-surface-2">
              <td className="p-3">
                <div className="text-nc-text font-medium">{s.display_name}</div>
                <div className="text-xs text-nc-text-dim">{s.skill_id}</div>
              </td>
              <td className="p-3 text-right text-nc-text">${s.total_spent.toFixed(4)}</td>
              <td className="p-3 text-right text-nc-text-dim">{s.execution_count}</td>
              <td className="p-3 text-right text-nc-text-dim">${s.avg_cost_per_run.toFixed(6)}</td>
              <td className="p-3 text-right text-nc-text-dim text-xs">
                {s.last_run ? new Date(s.last_run).toLocaleDateString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Usage Log ───────────────────────────────────────────────────────────────

function UsageLogView({ entries, total, page, onPageChange }: {
  entries: UsageLogEntry[] | null;
  total: number;
  page: number;
  onPageChange: (p: number) => void;
}) {
  if (!entries) return <LoadingState />;

  return (
    <div className="space-y-3">
      <div className="bg-nc-surface rounded-lg border border-nc-border overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-nc-border">
              <th className="text-left p-2 text-nc-text-dim font-medium">Time</th>
              <th className="text-left p-2 text-nc-text-dim font-medium">Provider</th>
              <th className="text-left p-2 text-nc-text-dim font-medium">Model</th>
              <th className="text-left p-2 text-nc-text-dim font-medium">Task Class</th>
              <th className="text-left p-2 text-nc-text-dim font-medium">Agent</th>
              <th className="text-right p-2 text-nc-text-dim font-medium">Tokens</th>
              <th className="text-right p-2 text-nc-text-dim font-medium">Cost</th>
              <th className="text-right p-2 text-nc-text-dim font-medium">Duration</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-nc-border/30 hover:bg-nc-surface-2">
                <td className="p-2 text-nc-text-dim">{new Date(e.timestamp).toLocaleTimeString()}</td>
                <td className="p-2 text-nc-text">{e.provider}</td>
                <td className="p-2 text-nc-text-dim">{e.model}</td>
                <td className="p-2 text-nc-text-dim">{e.task_class}</td>
                <td className="p-2 text-nc-text-dim">{e.agent_id || '—'}</td>
                <td className="p-2 text-right text-nc-text-dim">{e.input_tokens + e.output_tokens}</td>
                <td className="p-2 text-right text-nc-text">${e.cost_usd.toFixed(6)}</td>
                <td className="p-2 text-right text-nc-text-dim">{e.duration_ms}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Pagination */}
      <div className="flex items-center justify-between text-xs text-nc-text-dim">
        <span>{total} total entries</span>
        <div className="flex gap-2">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-2 py-1 rounded bg-nc-surface-2 disabled:opacity-40 hover:bg-nc-accent/20"
          >Prev</button>
          <span className="px-2 py-1">Page {page}</span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={entries.length < 50}
            className="px-2 py-1 rounded bg-nc-surface-2 disabled:opacity-40 hover:bg-nc-accent/20"
          >Next</button>
        </div>
      </div>
    </div>
  );
}

// ─── Shared ──────────────────────────────────────────────────────────────────

function SummaryCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
      <div className="text-xs text-nc-text-dim mb-1">{label}</div>
      <div className="text-xl font-bold text-nc-text">{value}</div>
      <div className="text-xs text-nc-text-dim mt-1">{sub}</div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-sm text-nc-text-dim animate-pulse">Loading...</div>
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function FinanceTab() {
  const [view, setView] = useState<SubView>('overview');
  const [budget, setBudget] = useState<BudgetOverview | null>(null);
  const [agentCosts, setAgentCosts] = useState<AgentCostBreakdown[] | null>(null);
  const [skillCosts, setSkillCosts] = useState<SkillCostBreakdown[] | null>(null);
  const [usageLog, setUsageLog] = useState<UsageLogEntry[] | null>(null);
  const [usageTotal, setUsageTotal] = useState(0);
  const [logPage, setLogPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async (v: SubView) => {
    setLoading(true);
    try {
      switch (v) {
        case 'overview':
        case 'providers': {
          const data = await fetchBudgetOverview();
          setBudget(data);
          break;
        }
        case 'agents': {
          const { agents } = await fetchBudgetByAgent();
          setAgentCosts(agents);
          break;
        }
        case 'skills': {
          const { skills } = await fetchBudgetBySkill();
          setSkillCosts(skills);
          break;
        }
        case 'log': {
          const data = await fetchUsageLog(logPage);
          setUsageLog(data.entries);
          setUsageTotal(data.total);
          break;
        }
      }
    } catch (err) {
      console.error('Finance load error:', err);
    } finally {
      setLoading(false);
    }
  }, [logPage]);

  useEffect(() => {
    loadData(view);
  }, [view, loadData]);

  const handleLogPage = (p: number) => {
    setLogPage(p);
    setView('log');
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-nc-border flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-nc-text">Finance & Budget</h1>
          <p className="text-xs text-nc-text-dim">LLM spend tracking across Anthropic, OpenAI, Google</p>
        </div>
        <button
          onClick={() => loadData(view)}
          className="px-3 py-1.5 text-xs rounded-lg bg-nc-surface-2 text-nc-text-dim hover:text-nc-text hover:bg-nc-accent/20 transition-colors"
        >Refresh</button>
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
        {view === 'overview' && <OverviewView data={budget} />}
        {view === 'providers' && <ProvidersView data={budget} />}
        {view === 'agents' && <AgentCostView agents={agentCosts} />}
        {view === 'skills' && <SkillCostView skills={skillCosts} />}
        {view === 'log' && <UsageLogView entries={usageLog} total={usageTotal} page={logPage} onPageChange={handleLogPage} />}
      </div>
    </div>
  );
}
