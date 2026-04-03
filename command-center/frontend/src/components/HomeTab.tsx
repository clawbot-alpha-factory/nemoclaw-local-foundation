'use client';

import { useState } from 'react';
import { clsx } from 'clsx';
import type { SystemState, HealthStatus, BridgeStatus } from '@/lib/types';
import { StatusCard, MiniBar, HealthDot } from './StatusCard';
import type { ConnectionStatus } from '@/hooks/useWebSocket';

interface HomeTabProps {
  state: SystemState | null;
  connectionStatus: ConnectionStatus;
  lastUpdate: Date | null;
  onRefresh: () => void;
}

export function HomeTab({ state, connectionStatus, lastUpdate, onRefresh }: HomeTabProps) {
  const [bridgesOpen, setBridgesOpen] = useState(false);
  const [budgetOpen, setBudgetOpen] = useState(false);

  if (!state) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <div className="text-nc-text-dim text-sm">
            {connectionStatus === 'connecting'
              ? 'Connecting to Command Center...'
              : connectionStatus === 'error'
              ? 'Connection failed. Is the backend running?'
              : 'Waiting for state...'}
          </div>
          {connectionStatus === 'error' && (
            <p className="text-nc-text-dim/60 text-xs mt-2 max-w-xs mx-auto">
              Run: cd command-center/backend && python run.py
            </p>
          )}
        </div>
      </div>
    );
  }

  const { skills, agents, ma_systems, bridges, budget, health, validation, frameworks } = state;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-nc-text">NemoClaw Command Center</h1>
          <p className="text-xs text-nc-text-dim mt-0.5">
            {state.git_branch && `${state.git_branch}`}
            {state.git_commit && ` · ${state.git_commit}`}
            {lastUpdate && ` · Updated ${formatAge(lastUpdate)}`}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 rounded-lg bg-nc-surface-2 border border-nc-border text-xs text-nc-text-dim hover:text-nc-text hover:border-nc-accent/50 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Overall Health Banner */}
      <OverallHealth status={health.overall} validation={validation} />

      {/* System Narrative */}
      {state.narrative && state.narrative.length > 0 && (
        <div className="glass rounded-xl border-l-2 border-nc-accent p-4">
          <h2 className="text-xs font-medium text-nc-accent uppercase tracking-wider mb-2">
            System Narrative
          </h2>
          <div className="space-y-1">
            {state.narrative.map((line: string, i: number) => (
              <p key={i} className="text-sm text-nc-text leading-relaxed">{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard
          title="Skills"
          value={skills.total_built}
          subtitle={`+ ${skills.total_registered} registered`}
          status={skills.total_built > 0 ? 'healthy' : 'warning'}
          icon="⚡"
        />
        <StatusCard
          title="Agents"
          value={agents.total}
          subtitle="configured"
          status={agents.total > 0 ? 'healthy' : 'warning'}
          icon="🤖"
        />
        <StatusCard
          title="MA Systems"
          value={`${ma_systems.total}/20`}
          subtitle={`${ma_systems.total_tests} tests`}
          status={ma_systems.total >= 20 ? 'healthy' : 'warning'}
          icon="🔗"
        />
        <StatusCard
          title="Frameworks"
          value={frameworks.total}
          subtitle="production"
          status={frameworks.total > 0 ? 'healthy' : 'unknown'}
          icon="🏗"
        />
      </div>

      {/* Bridges + Budget — collapsible */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Bridges */}
        <Collapsible
          title="🌉 Bridges"
          count={bridges.total}
          right={`${bridges.connected} connected · ${bridges.total_tests} tests`}
          open={bridgesOpen}
          onToggle={() => setBridgesOpen(!bridgesOpen)}
        >
          <div className="space-y-2">
            {bridges.bridges.map((b) => (
              <div key={b.bridge_id} className="flex items-center gap-2">
                <BridgeStatusDot status={b.status} />
                <span className="text-xs text-nc-text flex-1 truncate">{b.name}</span>
                <span className="text-xs text-nc-text-dim">{b.test_pass}/{b.test_count}</span>
              </div>
            ))}
            {bridges.bridges.length === 0 && (
              <p className="text-xs text-nc-text-dim">No bridges found</p>
            )}
          </div>
        </Collapsible>

        {/* Budget */}
        <Collapsible
          title="💰 Budget"
          right={`$${budget.total_spent.toFixed(2)} / $${budget.total_limit.toFixed(2)}`}
          open={budgetOpen}
          onToggle={() => setBudgetOpen(!budgetOpen)}
        >
          <div className="space-y-3">
            {budget.providers.map((p) => (
              <div key={p.provider}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-nc-text capitalize">{p.provider}</span>
                  <span className="text-xs text-nc-text-dim">
                    ${p.spent.toFixed(2)} / ${p.limit.toFixed(2)} ({p.percent_used.toFixed(0)}%)
                  </span>
                </div>
                <MiniBar
                  value={p.spent}
                  max={p.limit}
                  color={
                    p.percent_used > 80 ? 'bg-nc-red'
                    : p.percent_used > 50 ? 'bg-nc-yellow'
                    : 'bg-nc-green'
                  }
                />
              </div>
            ))}
            {budget.providers.length === 0 && (
              <p className="text-xs text-nc-text-dim">No budget data</p>
            )}
          </div>
        </Collapsible>
      </div>

      {/* Health Domains */}
      <div className="glass rounded-xl p-4">
        <h2 className="text-sm font-medium text-nc-text-dim uppercase tracking-wider mb-3">
          🏥 Health Domains
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6">
          {health.domains.map((d) => (
            <HealthDot
              key={d.domain}
              status={d.status}
              label={formatDomainLabel(d.domain)}
              message={d.message}
            />
          ))}
        </div>
      </div>

      {/* Validation Footer Bar */}
      <div className="flex items-center gap-6 text-xs text-nc-text-dim pt-2 border-t border-nc-border/50">
        <span>Validation:</span>
        <span className="text-nc-green font-medium">{validation.passed} pass</span>
        {validation.warnings > 0 && <span className="text-nc-yellow font-medium">{validation.warnings} warn</span>}
        {validation.failed > 0 && <span className="text-nc-red font-medium">{validation.failed} fail</span>}
        <span className="text-nc-text-dim/50 ml-auto">
          v{state.version} · state #{state.state_version}
        </span>
      </div>
    </div>
  );
}


// Sub-components

function OverallHealth({
  status,
  validation,
}: {
  status: HealthStatus;
  validation: SystemState['validation'];
}) {
  const config: Record<HealthStatus, { bg: string; border: string; text: string; dot: string; label: string }> = {
    healthy: {
      bg: 'bg-nc-green/5', border: 'border-nc-green/20', text: 'text-nc-green',
      dot: 'bg-nc-green', label: 'All Systems Operational',
    },
    warning: {
      bg: 'bg-nc-yellow/5', border: 'border-nc-yellow/20', text: 'text-nc-yellow',
      dot: 'bg-nc-yellow', label: 'Warnings Detected',
    },
    error: {
      bg: 'bg-nc-red/5', border: 'border-nc-red/20', text: 'text-nc-red',
      dot: 'bg-nc-red', label: 'Issues Detected',
    },
    unknown: {
      bg: 'bg-nc-surface', border: 'border-nc-border', text: 'text-nc-text-dim',
      dot: 'bg-nc-text-dim', label: 'Status Unknown',
    },
  };

  const c = config[status];

  return (
    <div className={clsx('rounded-xl border p-4 flex items-center justify-between', c.bg, c.border)}>
      <div className="flex items-center gap-3">
        <div className={clsx('w-3 h-3 rounded-full', c.dot)} />
        <span className={clsx('text-sm font-medium', c.text)}>{c.label}</span>
      </div>
      <div className="flex items-center gap-4 text-xs text-nc-text-dim">
        <span>{validation.passed} pass</span>
        {validation.warnings > 0 && <span className="text-nc-yellow">{validation.warnings} warn</span>}
        {validation.failed > 0 && <span className="text-nc-red">{validation.failed} fail</span>}
      </div>
    </div>
  );
}

function Collapsible({
  title,
  count,
  right,
  open,
  onToggle,
  children,
}: {
  title: string;
  count?: number;
  right: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="glass rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-nc-surface-2/50 transition-colors"
      >
        <h2 className="text-sm font-medium text-nc-text-dim uppercase tracking-wider">
          {title}{count !== undefined ? ` (${count})` : ''}
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-nc-text-dim">{right}</span>
          <svg
            className={clsx('w-3 h-3 text-nc-text-dim transition-transform duration-200', open && 'rotate-180')}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-0">
          {children}
        </div>
      )}
    </div>
  );
}

function BridgeStatusDot({ status }: { status: BridgeStatus }) {
  const color: Record<BridgeStatus, string> = {
    connected: 'bg-nc-green',
    mocked: 'bg-nc-yellow',
    error: 'bg-nc-red',
    unconfigured: 'bg-nc-text-dim/40',
  };
  return <div className={clsx('w-2 h-2 rounded-full shrink-0', color[status])} />;
}

function formatAge(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

function formatDomainLabel(domain: string): string {
  return domain.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
