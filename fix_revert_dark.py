#!/usr/bin/env python3
"""
Revert to original dark design with:
  - Collapsible Bridges and Budget sections
  - Clean validation footer bar (from modern design)
  - No skill families section
Usage: cd ~/nemoclaw-local-foundation && python3 fix_revert_dark.py
"""

import os, sys

BASE = "command-center/frontend/src"
CHECK = f"{BASE}/app/globals.css"

if not os.path.exists(CHECK):
    print(f"ERROR: {CHECK} not found. Run from ~/nemoclaw-local-foundation/")
    sys.exit(1)


def write(path, content):
    with open(path, "w") as f:
        f.write(content)
    print(f"  Updated {path}")


# ═══════════════════════════════════════════════════════════════════
# 1. GLOBALS.CSS — original dark
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/app/globals.css", """\
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --nc-bg: #0a0a0f;
  --nc-surface: #12121a;
  --nc-surface-2: #1a1a25;
  --nc-border: #2a2a3a;
  --nc-accent: #6366f1;
  --nc-green: #22c55e;
  --nc-yellow: #eab308;
  --nc-red: #ef4444;
  --nc-text: #e2e2ea;
  --nc-text-dim: #8888a0;
}

body {
  background-color: var(--nc-bg);
  color: var(--nc-text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--nc-bg); }
::-webkit-scrollbar-thumb { background: var(--nc-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--nc-text-dim); }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}
""")


# ═══════════════════════════════════════════════════════════════════
# 2. TAILWIND CONFIG — original dark
# ═══════════════════════════════════════════════════════════════════

write("command-center/frontend/tailwind.config.js", """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        'nc-bg': '#0a0a0f',
        'nc-surface': '#12121a',
        'nc-surface-2': '#1a1a25',
        'nc-border': '#2a2a3a',
        'nc-accent': '#6366f1',
        'nc-accent-dim': '#4f46e5',
        'nc-green': '#22c55e',
        'nc-yellow': '#eab308',
        'nc-red': '#ef4444',
        'nc-text': '#e2e2ea',
        'nc-text-dim': '#8888a0',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
""")


# ═══════════════════════════════════════════════════════════════════
# 3. SIDEBAR — original dark compact sidebar
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/Sidebar.tsx", """\
'use client';

import { clsx } from 'clsx';
import type { TabId } from '@/lib/types';
import type { ConnectionStatus } from '@/hooks/useWebSocket';

interface NavItem {
  id: TabId;
  label: string;
  emoji: string;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home', label: 'Home', emoji: '\\u2302' },
  { id: 'communications', label: 'Comms', emoji: '\\ud83d\\udcac', disabled: true },
  { id: 'agents', label: 'Agents', emoji: '\\ud83e\\udd16', disabled: true },
  { id: 'skills', label: 'Skills', emoji: '\\u26a1', disabled: true },
  { id: 'operations', label: 'Ops', emoji: '\\ud83d\\udcca', disabled: true },
  { id: 'finance', label: 'Finance', emoji: '\\ud83d\\udcb0', disabled: true },
  { id: 'projects', label: 'Projects', emoji: '\\ud83d\\udccb', disabled: true },
  { id: 'clients', label: 'Clients', emoji: '\\ud83c\\udfe2', disabled: true },
  { id: 'approvals', label: 'Approvals', emoji: '\\u2705', disabled: true },
  { id: 'intelligence', label: 'Intel', emoji: '\\ud83e\\udde0', disabled: true },
  { id: 'settings', label: 'Settings', emoji: '\\u2699\\ufe0f', disabled: true },
];

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  connectionStatus: ConnectionStatus;
}

export function Sidebar({ activeTab, onTabChange, connectionStatus }: SidebarProps) {
  const statusColor = {
    connected: 'bg-nc-green',
    connecting: 'bg-nc-yellow animate-pulse-dot',
    disconnected: 'bg-nc-red',
    error: 'bg-nc-red',
  }[connectionStatus];

  return (
    <aside className="w-16 bg-nc-surface border-r border-nc-border flex flex-col items-center py-4 shrink-0">
      <div className="mb-6 flex flex-col items-center gap-1">
        <div className="w-9 h-9 rounded-lg bg-nc-accent flex items-center justify-center text-white font-bold text-sm">
          NC
        </div>
        <div className={clsx('w-2 h-2 rounded-full mt-1', statusColor)} />
      </div>

      <nav className="flex flex-col gap-1 flex-1 w-full px-1.5">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => !item.disabled && onTabChange(item.id)}
            disabled={item.disabled}
            title={item.label}
            className={clsx(
              'w-full aspect-square rounded-lg flex flex-col items-center justify-center text-xs gap-0.5 transition-colors',
              activeTab === item.id
                ? 'bg-nc-accent/20 text-nc-accent'
                : item.disabled
                ? 'text-nc-text-dim/40 cursor-not-allowed'
                : 'text-nc-text-dim hover:bg-nc-surface-2 hover:text-nc-text'
            )}
          >
            <span className="text-base">{item.emoji}</span>
            <span className="text-[9px] leading-none">{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
""")


# ═══════════════════════════════════════════════════════════════════
# 4. STATUS CARD — original dark
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/StatusCard.tsx", """\
'use client';

import { clsx } from 'clsx';
import type { HealthStatus } from '@/lib/types';

interface StatusCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  status?: HealthStatus;
  icon?: string;
  children?: React.ReactNode;
}

const STATUS_COLORS: Record<HealthStatus, string> = {
  healthy: 'border-nc-green/30 bg-nc-green/5',
  warning: 'border-nc-yellow/30 bg-nc-yellow/5',
  error: 'border-nc-red/30 bg-nc-red/5',
  unknown: 'border-nc-border bg-nc-surface',
};

const STATUS_DOT: Record<HealthStatus, string> = {
  healthy: 'bg-nc-green',
  warning: 'bg-nc-yellow',
  error: 'bg-nc-red',
  unknown: 'bg-nc-text-dim',
};

export function StatusCard({ title, value, subtitle, status = 'unknown', icon, children }: StatusCardProps) {
  return (
    <div className={clsx('rounded-xl border p-4 transition-colors', STATUS_COLORS[status])}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon && <span className="text-lg">{icon}</span>}
          <span className="text-xs font-medium text-nc-text-dim uppercase tracking-wider">{title}</span>
        </div>
        <div className={clsx('w-2 h-2 rounded-full mt-1', STATUS_DOT[status])} />
      </div>
      <div className="text-2xl font-bold text-nc-text mb-0.5">{value}</div>
      {subtitle && <div className="text-xs text-nc-text-dim">{subtitle}</div>}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}

interface MiniBarProps {
  value: number;
  max: number;
  color?: string;
}

export function MiniBar({ value, max, color = 'bg-nc-accent' }: MiniBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-1.5 rounded-full bg-nc-border overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

interface HealthDotProps {
  status: HealthStatus;
  label: string;
  message?: string;
}

export function HealthDot({ status, label, message }: HealthDotProps) {
  return (
    <div className="flex items-center gap-2 py-1">
      <div className={clsx('w-2 h-2 rounded-full shrink-0', STATUS_DOT[status])} />
      <span className="text-xs text-nc-text flex-1">{label}</span>
      {message && (
        <span className="text-xs text-nc-text-dim truncate max-w-[180px]">{message}</span>
      )}
    </div>
  );
}
""")


# ═══════════════════════════════════════════════════════════════════
# 5. HOME TAB — original dark + collapsible Bridges/Budget + footer
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/HomeTab.tsx", """\
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
          <div className="text-4xl mb-4">\\u23f3</div>
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
            {state.git_commit && ` \\u00b7 ${state.git_commit}`}
            {lastUpdate && ` \\u00b7 Updated ${formatAge(lastUpdate)}`}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 rounded-lg bg-nc-surface-2 border border-nc-border text-xs text-nc-text-dim hover:text-nc-text hover:border-nc-accent/50 transition-colors"
        >
          \\u21bb Refresh
        </button>
      </div>

      {/* Overall Health Banner */}
      <OverallHealth status={health.overall} validation={validation} />

      {/* System Narrative */}
      {state.narrative && state.narrative.length > 0 && (
        <div className="rounded-xl border border-nc-accent/20 bg-nc-accent/5 p-4">
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
          icon="\\u26a1"
        />
        <StatusCard
          title="Agents"
          value={agents.total}
          subtitle="configured"
          status={agents.total > 0 ? 'healthy' : 'warning'}
          icon="\\ud83e\\udd16"
        />
        <StatusCard
          title="MA Systems"
          value={`${ma_systems.total}/20`}
          subtitle={`${ma_systems.total_tests} tests`}
          status={ma_systems.total >= 20 ? 'healthy' : 'warning'}
          icon="\\ud83d\\udd17"
        />
        <StatusCard
          title="Frameworks"
          value={frameworks.total}
          subtitle="production"
          status={frameworks.total > 0 ? 'healthy' : 'unknown'}
          icon="\\ud83c\\udfd7\\ufe0f"
        />
      </div>

      {/* Bridges + Budget — collapsible */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Bridges */}
        <Collapsible
          title={`\\ud83c\\udf09 Bridges (${bridges.total})`}
          right={`${bridges.connected} connected \\u00b7 ${bridges.total_tests} tests`}
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
          title="\\ud83d\\udcb0 Budget"
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
      <div className="rounded-xl border border-nc-border bg-nc-surface p-4">
        <h2 className="text-sm font-medium text-nc-text-dim uppercase tracking-wider mb-3">
          \\ud83c\\udfe5 Health Domains
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
          v{state.version} \\u00b7 state #{state.state_version}
        </span>
      </div>
    </div>
  );
}


// \\u2500\\u2500 Sub-components \\u2500\\u2500

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
  right,
  open,
  onToggle,
  children,
}: {
  title: string;
  right: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-nc-border bg-nc-surface overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-nc-surface-2 transition-colors"
      >
        <h2 className="text-sm font-medium text-nc-text-dim uppercase tracking-wider">
          {title}
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-nc-text-dim">{right}</span>
          <span className={clsx(
            'text-nc-text-dim text-xs transition-transform duration-200',
            open ? 'rotate-180' : ''
          )}>
            \\u25bc
          </span>
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
  return domain.replace(/_/g, ' ').replace(/\\b\\w/g, (c) => c.toUpperCase());
}
""")


# ═══════════════════════════════════════════════════════════════════
# 6. PAGE — original dark
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/app/page.tsx", """\
'use client';

import { useState } from 'react';
import type { TabId } from '@/lib/types';
import { Sidebar } from '@/components/Sidebar';
import { HomeTab } from '@/components/HomeTab';
import { useWebSocket } from '@/hooks/useWebSocket';

export default function CommandCenter() {
  const [activeTab, setActiveTab] = useState<TabId>('home');
  const { state, status, lastUpdate, refresh } = useWebSocket();

  return (
    <div className="h-screen flex overflow-hidden bg-nc-bg">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        connectionStatus={status}
      />

      <main className="flex-1 overflow-hidden">
        {activeTab === 'home' && (
          <HomeTab
            state={state}
            connectionStatus={status}
            lastUpdate={lastUpdate}
            onRefresh={refresh}
          />
        )}

        {activeTab !== 'home' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-4xl mb-3">\\ud83d\\udea7</div>
              <div className="text-sm text-nc-text-dim">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} \\u2014 Coming in CC-{getPhase(activeTab)}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function getPhase(tab: TabId): string {
  const phases: Record<TabId, string> = {
    home: '1', communications: '3', agents: '4', skills: '5',
    operations: '6', finance: '6', projects: '7', clients: '8',
    approvals: '9', intelligence: '9', settings: '10', playground: '10',
  };
  return phases[tab] || '?';
}
""")

print("\\nDark design restored with collapsible Bridges/Budget and validation footer.")
print("Refresh http://localhost:3000")
