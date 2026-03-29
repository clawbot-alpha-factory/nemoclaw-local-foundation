#!/usr/bin/env python3
"""
Modernize Command Center UI — cleaner, simpler, more polished.
Usage: cd ~/nemoclaw-local-foundation && python3 fix_modern_ui.py
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
# 1. GLOBALS.CSS
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/app/globals.css", """\
@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --nc-bg: #ffffff;
  --nc-surface: #fafafa;
  --nc-surface-2: #f4f4f5;
  --nc-border: #e4e4e7;
  --nc-border-light: #f0f0f2;
  --nc-accent: #6366f1;
  --nc-green: #10b981;
  --nc-yellow: #f59e0b;
  --nc-red: #ef4444;
  --nc-text: #18181b;
  --nc-text-dim: #71717a;
  --nc-text-faint: #a1a1aa;
}

body {
  background-color: var(--nc-bg);
  color: var(--nc-text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  -webkit-font-smoothing: antialiased;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--nc-border); border-radius: 2px; }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse-dot {
  animation: pulse-dot 2s ease-in-out infinite;
}
""")


# ═══════════════════════════════════════════════════════════════════
# 2. TAILWIND CONFIG
# ═══════════════════════════════════════════════════════════════════

write("command-center/frontend/tailwind.config.js", """\
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        'nc-bg': '#ffffff',
        'nc-surface': '#fafafa',
        'nc-surface-2': '#f4f4f5',
        'nc-border': '#e4e4e7',
        'nc-border-light': '#f0f0f2',
        'nc-accent': '#6366f1',
        'nc-accent-dim': '#4f46e5',
        'nc-green': '#10b981',
        'nc-yellow': '#f59e0b',
        'nc-red': '#ef4444',
        'nc-text': '#18181b',
        'nc-text-dim': '#71717a',
        'nc-text-faint': '#a1a1aa',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.06)',
      },
    },
  },
  plugins: [],
};
""")


# ═══════════════════════════════════════════════════════════════════
# 3. SIDEBAR — clean minimal nav
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/Sidebar.tsx", """\
'use client';

import { clsx } from 'clsx';
import type { TabId } from '@/lib/types';
import type { ConnectionStatus } from '@/hooks/useWebSocket';

interface NavItem {
  id: TabId;
  label: string;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home', label: 'Home' },
  { id: 'communications', label: 'Comms', disabled: true },
  { id: 'agents', label: 'Agents', disabled: true },
  { id: 'skills', label: 'Skills', disabled: true },
  { id: 'operations', label: 'Ops', disabled: true },
  { id: 'finance', label: 'Finance', disabled: true },
  { id: 'projects', label: 'Projects', disabled: true },
  { id: 'clients', label: 'Clients', disabled: true },
  { id: 'approvals', label: 'Approvals', disabled: true },
  { id: 'intelligence', label: 'Intel', disabled: true },
  { id: 'settings', label: 'Settings', disabled: true },
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
    <aside className="w-52 border-r border-nc-border bg-nc-surface flex flex-col shrink-0 h-screen">
      {/* Header */}
      <div className="px-5 py-5 border-b border-nc-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-nc-accent flex items-center justify-center text-white text-xs font-bold">
            NC
          </div>
          <div>
            <div className="text-sm font-semibold text-nc-text leading-tight">NemoClaw</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className={clsx('w-1.5 h-1.5 rounded-full', statusColor)} />
              <span className="text-[10px] text-nc-text-dim capitalize">{connectionStatus}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2.5 overflow-y-auto">
        <div className="space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => !item.disabled && onTabChange(item.id)}
              disabled={item.disabled}
              className={clsx(
                'w-full text-left px-3 py-2 rounded-lg text-[13px] transition-all',
                activeTab === item.id
                  ? 'bg-nc-accent text-white font-medium'
                  : item.disabled
                  ? 'text-nc-text-faint cursor-not-allowed'
                  : 'text-nc-text-dim hover:bg-nc-surface-2 hover:text-nc-text'
              )}
            >
              {item.label}
              {item.disabled && (
                <span className="ml-1.5 text-[10px] opacity-50">soon</span>
              )}
            </button>
          ))}
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-nc-border">
        <span className="text-[10px] text-nc-text-faint">Command Center v1.0</span>
      </div>
    </aside>
  );
}
""")


# ═══════════════════════════════════════════════════════════════════
# 4. STATUS CARD — clean shadow-based cards
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
  children?: React.ReactNode;
}

const STATUS_ACCENT: Record<HealthStatus, string> = {
  healthy: 'border-l-nc-green',
  warning: 'border-l-nc-yellow',
  error: 'border-l-nc-red',
  unknown: 'border-l-nc-border',
};

export function StatusCard({ title, value, subtitle, status = 'unknown', children }: StatusCardProps) {
  return (
    <div className={clsx(
      'bg-white rounded-xl shadow-card border border-nc-border-light p-5 border-l-[3px] transition-shadow hover:shadow-card-hover',
      STATUS_ACCENT[status]
    )}>
      <div className="text-xs font-medium text-nc-text-dim uppercase tracking-wide">{title}</div>
      <div className="text-3xl font-bold text-nc-text mt-1.5">{value}</div>
      {subtitle && <div className="text-xs text-nc-text-dim mt-1">{subtitle}</div>}
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
    <div className="h-1.5 rounded-full bg-nc-surface-2 overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all duration-500', color)}
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

const DOT_COLOR: Record<HealthStatus, string> = {
  healthy: 'bg-nc-green',
  warning: 'bg-nc-yellow',
  error: 'bg-nc-red',
  unknown: 'bg-nc-text-faint',
};

export function HealthDot({ status, label, message }: HealthDotProps) {
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <div className={clsx('w-2 h-2 rounded-full shrink-0', DOT_COLOR[status])} />
      <span className="text-[13px] text-nc-text flex-1">{label}</span>
      {message && (
        <span className="text-[11px] text-nc-text-dim truncate max-w-[200px]">{message}</span>
      )}
    </div>
  );
}
""")


# ═══════════════════════════════════════════════════════════════════
# 5. HOME TAB — modern clean layout
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/HomeTab.tsx", """\
'use client';

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
  if (!state) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-3xl mb-3 opacity-30">
            {connectionStatus === 'error' ? '!' : '...'}
          </div>
          <div className="text-sm text-nc-text-dim">
            {connectionStatus === 'connecting' ? 'Connecting...'
              : connectionStatus === 'error' ? 'Backend not reachable'
              : 'Waiting for state...'}
          </div>
          {connectionStatus === 'error' && (
            <p className="text-xs text-nc-text-faint mt-2">
              Run: cd command-center/backend && python run.py
            </p>
          )}
        </div>
      </div>
    );
  }

  const { skills, agents, ma_systems, bridges, budget, health, validation, frameworks } = state;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8 overflow-y-auto h-full">

      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-nc-text">Command Center</h1>
          <p className="text-sm text-nc-text-dim mt-1">
            {state.git_branch && <span>{state.git_branch}</span>}
            {state.git_commit && <span className="ml-1 text-nc-text-faint">@ {state.git_commit}</span>}
            {lastUpdate && <span className="ml-2 text-nc-text-faint">{formatAge(lastUpdate)}</span>}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-4 py-2 rounded-lg bg-nc-surface-2 text-xs font-medium text-nc-text-dim hover:text-nc-text hover:bg-nc-border transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Narrative */}
      {state.narrative && state.narrative.length > 0 && (
        <div className="bg-indigo-50 rounded-xl px-6 py-4">
          <div className="space-y-1">
            {state.narrative.map((line: string, i: number) => (
              <p key={i} className="text-[13px] text-indigo-900 leading-relaxed">{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Skills"
          value={skills.total_built}
          subtitle={`${skills.total_registered} registered`}
          status={skills.total_built > 0 ? 'healthy' : 'warning'}
        />
        <StatusCard
          title="Agents"
          value={agents.total}
          subtitle="configured"
          status={agents.total > 0 ? 'healthy' : 'warning'}
        />
        <StatusCard
          title="MA Systems"
          value={`${ma_systems.total}/20`}
          subtitle={`${ma_systems.total_tests} tests`}
          status={ma_systems.total >= 20 ? 'healthy' : 'warning'}
        />
        <StatusCard
          title="Frameworks"
          value={frameworks.total}
          subtitle="production"
          status={frameworks.total > 0 ? 'healthy' : 'unknown'}
        />
      </div>

      {/* Bridges + Budget */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Bridges */}
        <Section title="Bridges" right={`${bridges.connected} connected / ${bridges.total}`}>
          <div className="space-y-2.5">
            {bridges.bridges.map((b) => (
              <div key={b.bridge_id} className="flex items-center gap-2.5">
                <BridgeDot status={b.status} />
                <span className="text-[13px] text-nc-text flex-1">{b.name}</span>
                <span className="text-xs text-nc-text-faint font-mono">{b.test_pass}/{b.test_count}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Budget */}
        <Section title="Budget" right={`$${budget.total_spent.toFixed(2)} / $${budget.total_limit.toFixed(2)}`}>
          <div className="space-y-4">
            {budget.providers.map((p) => (
              <div key={p.provider}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] text-nc-text capitalize">{p.provider}</span>
                  <span className="text-xs text-nc-text-dim font-mono">
                    ${p.spent.toFixed(2)} / ${p.limit.toFixed(2)}
                  </span>
                </div>
                <MiniBar
                  value={p.spent}
                  max={p.limit}
                  color={p.percent_used > 80 ? 'bg-nc-red' : p.percent_used > 50 ? 'bg-nc-yellow' : 'bg-nc-green'}
                />
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* Health + Validation */}
      <Section
        title="System Health"
        right={
          <span className={clsx('text-xs font-medium',
            health.overall === 'healthy' ? 'text-nc-green'
            : health.overall === 'warning' ? 'text-nc-yellow'
            : 'text-nc-red'
          )}>
            {health.overall === 'healthy' ? 'All operational'
             : health.overall === 'warning' ? 'Warnings'
             : 'Issues detected'}
          </span>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8">
          {health.domains.map((d) => (
            <HealthDot
              key={d.domain}
              status={d.status}
              label={d.domain.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase())}
              message={d.message}
            />
          ))}
        </div>
      </Section>

      {/* Validation bar */}
      <div className="flex items-center gap-6 text-xs text-nc-text-dim">
        <span>Validation:</span>
        <span className="text-nc-green font-medium">{validation.passed} pass</span>
        {validation.warnings > 0 && <span className="text-nc-yellow font-medium">{validation.warnings} warn</span>}
        {validation.failed > 0 && <span className="text-nc-red font-medium">{validation.failed} fail</span>}
        <span className="text-nc-text-faint ml-auto">v{state.version} &middot; state #{state.state_version}</span>
      </div>
    </div>
  );
}


// ── Helpers ──────────────────────────────────────────────────────────

function Section({ title, right, children }: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl shadow-card border border-nc-border-light p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-nc-text">{title}</h2>
        {right && <span className="text-xs text-nc-text-dim">{typeof right === 'string' ? right : right}</span>}
      </div>
      {children}
    </div>
  );
}

function BridgeDot({ status }: { status: BridgeStatus }) {
  const color: Record<BridgeStatus, string> = {
    connected: 'bg-nc-green',
    mocked: 'bg-nc-yellow',
    error: 'bg-nc-red',
    unconfigured: 'bg-nc-text-faint',
  };
  return <div className={clsx('w-2 h-2 rounded-full shrink-0', color[status])} />;
}

function formatAge(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}
""")


# ═══════════════════════════════════════════════════════════════════
# 6. MAIN PAGE — cleaner layout
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
    <div className="h-screen flex overflow-hidden bg-white">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        connectionStatus={status}
      />

      <main className="flex-1 overflow-hidden bg-nc-bg">
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
              <div className="text-sm text-nc-text-dim">
                <span className="font-medium text-nc-text">
                  {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
                </span>
                {' '}ships in Phase CC-{getPhase(activeTab)}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function getPhase(tab: TabId): string {
  const p: Record<TabId, string> = {
    home:'1', communications:'3', agents:'4', skills:'5', operations:'6',
    finance:'6', projects:'7', clients:'8', approvals:'9', intelligence:'9',
    settings:'10', playground:'10',
  };
  return p[tab] || '?';
}
""")


print("\nModern UI applied. Refresh http://localhost:3000")
