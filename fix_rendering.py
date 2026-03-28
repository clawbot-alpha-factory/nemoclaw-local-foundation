#!/usr/bin/env python3
"""
Fix all rendering issues:
  1. Emoji unicode escapes showing as literal text
  2. Bridge test counts showing 0/0
  3. Sidebar dark vs white mismatch
Usage: cd ~/nemoclaw-local-foundation && python3 fix_rendering.py
"""

import os, sys

BASE = "command-center/frontend/src"
BACKEND = "command-center/backend/app"

if not os.path.exists(f"{BASE}/app/globals.css"):
    print("ERROR: Run from ~/nemoclaw-local-foundation/")
    sys.exit(1)

fixes = 0

def write(path, content):
    global fixes
    with open(path, "w") as f:
        f.write(content)
    fixes += 1
    print(f"  [{fixes}] {path}")


# ═══════════════════════════════════════════════════════════════════
# FIX 1: Sidebar — white background, real emoji characters
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/Sidebar.tsx", '''\'use client\';

import { clsx } from \'clsx\';
import type { TabId } from \'@/lib/types\';
import type { ConnectionStatus } from \'@/hooks/useWebSocket\';

interface NavItem {
  id: TabId;
  label: string;
  emoji: string;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { id: \'home\', label: \'Home\', emoji: \'\u2302\' },
  { id: \'communications\', label: \'Comms\', emoji: \'\U0001f4ac\', disabled: true },
  { id: \'agents\', label: \'Agents\', emoji: \'\U0001f916\', disabled: true },
  { id: \'skills\', label: \'Skills\', emoji: \'\u26a1\', disabled: true },
  { id: \'operations\', label: \'Ops\', emoji: \'\U0001f4ca\', disabled: true },
  { id: \'finance\', label: \'Finance\', emoji: \'\U0001f4b0\', disabled: true },
  { id: \'projects\', label: \'Projects\', emoji: \'\U0001f4cb\', disabled: true },
  { id: \'clients\', label: \'Clients\', emoji: \'\U0001f3e2\', disabled: true },
  { id: \'approvals\', label: \'Approvals\', emoji: \'\u2705\', disabled: true },
  { id: \'intelligence\', label: \'Intel\', emoji: \'\U0001f9e0\', disabled: true },
  { id: \'settings\', label: \'Settings\', emoji: \'\u2699\', disabled: true },
];

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  connectionStatus: ConnectionStatus;
}

export function Sidebar({ activeTab, onTabChange, connectionStatus }: SidebarProps) {
  const statusColor = {
    connected: \'bg-nc-green\',
    connecting: \'bg-nc-yellow animate-pulse-dot\',
    disconnected: \'bg-nc-red\',
    error: \'bg-nc-red\',
  }[connectionStatus];

  return (
    <aside className="w-16 bg-nc-surface border-r border-nc-border flex flex-col items-center py-4 shrink-0">
      <div className="mb-6 flex flex-col items-center gap-1">
        <div className="w-9 h-9 rounded-lg bg-nc-accent flex items-center justify-center text-white font-bold text-sm">
          NC
        </div>
        <div className={clsx(\'w-2 h-2 rounded-full mt-1\', statusColor)} />
      </div>

      <nav className="flex flex-col gap-1 flex-1 w-full px-1.5">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => !item.disabled && onTabChange(item.id)}
            disabled={item.disabled}
            title={item.label}
            className={clsx(
              \'w-full aspect-square rounded-lg flex flex-col items-center justify-center text-xs gap-0.5 transition-colors\',
              activeTab === item.id
                ? \'bg-nc-accent/20 text-nc-accent\'
                : item.disabled
                ? \'text-nc-text-dim/40 cursor-not-allowed\'
                : \'text-nc-text-dim hover:bg-nc-surface-2 hover:text-nc-text\'
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
''')


# ═══════════════════════════════════════════════════════════════════
# FIX 2: HomeTab — real emojis, fix dropdown arrows
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/components/HomeTab.tsx", '''\'use client\';

import { useState } from \'react\';
import { clsx } from \'clsx\';
import type { SystemState, HealthStatus, BridgeStatus } from \'@/lib/types\';
import { StatusCard, MiniBar, HealthDot } from \'./StatusCard\';
import type { ConnectionStatus } from \'@/hooks/useWebSocket\';

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
          <div className="text-4xl mb-4">\u23f3</div>
          <div className="text-nc-text-dim text-sm">
            {connectionStatus === \'connecting\'
              ? \'Connecting to Command Center...\'
              : connectionStatus === \'error\'
              ? \'Connection failed. Is the backend running?\'
              : \'Waiting for state...\'}
          </div>
          {connectionStatus === \'error\' && (
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
            {state.git_commit && ` \u00b7 ${state.git_commit}`}
            {lastUpdate && ` \u00b7 Updated ${formatAge(lastUpdate)}`}
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 rounded-lg bg-nc-surface-2 border border-nc-border text-xs text-nc-text-dim hover:text-nc-text hover:border-nc-accent/50 transition-colors"
        >
          \u21bb Refresh
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
          status={skills.total_built > 0 ? \'healthy\' : \'warning\'}
          icon="\u26a1"
        />
        <StatusCard
          title="Agents"
          value={agents.total}
          subtitle="configured"
          status={agents.total > 0 ? \'healthy\' : \'warning\'}
          icon="\U0001f916"
        />
        <StatusCard
          title="MA Systems"
          value={`${ma_systems.total}/20`}
          subtitle={`${ma_systems.total_tests} tests`}
          status={ma_systems.total >= 20 ? \'healthy\' : \'warning\'}
          icon="\U0001f517"
        />
        <StatusCard
          title="Frameworks"
          value={frameworks.total}
          subtitle="production"
          status={frameworks.total > 0 ? \'healthy\' : \'unknown\'}
          icon="\U0001f3d7"
        />
      </div>

      {/* Bridges + Budget \u2014 collapsible */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Bridges */}
        <Collapsible
          title="\U0001f309 Bridges"
          count={bridges.total}
          right={`${bridges.connected} connected \u00b7 ${bridges.total_tests} tests`}
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
          title="\U0001f4b0 Budget"
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
                    p.percent_used > 80 ? \'bg-nc-red\'
                    : p.percent_used > 50 ? \'bg-nc-yellow\'
                    : \'bg-nc-green\'
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
          \U0001f3e5 Health Domains
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
          v{state.version} \u00b7 state #{state.state_version}
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
  validation: SystemState[\'validation\'];
}) {
  const config: Record<HealthStatus, { bg: string; border: string; text: string; dot: string; label: string }> = {
    healthy: {
      bg: \'bg-nc-green/5\', border: \'border-nc-green/20\', text: \'text-nc-green\',
      dot: \'bg-nc-green\', label: \'All Systems Operational\',
    },
    warning: {
      bg: \'bg-nc-yellow/5\', border: \'border-nc-yellow/20\', text: \'text-nc-yellow\',
      dot: \'bg-nc-yellow\', label: \'Warnings Detected\',
    },
    error: {
      bg: \'bg-nc-red/5\', border: \'border-nc-red/20\', text: \'text-nc-red\',
      dot: \'bg-nc-red\', label: \'Issues Detected\',
    },
    unknown: {
      bg: \'bg-nc-surface\', border: \'border-nc-border\', text: \'text-nc-text-dim\',
      dot: \'bg-nc-text-dim\', label: \'Status Unknown\',
    },
  };

  const c = config[status];

  return (
    <div className={clsx(\'rounded-xl border p-4 flex items-center justify-between\', c.bg, c.border)}>
      <div className="flex items-center gap-3">
        <div className={clsx(\'w-3 h-3 rounded-full\', c.dot)} />
        <span className={clsx(\'text-sm font-medium\', c.text)}>{c.label}</span>
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
    <div className="rounded-xl border border-nc-border bg-nc-surface overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-nc-surface-2 transition-colors"
      >
        <h2 className="text-sm font-medium text-nc-text-dim uppercase tracking-wider">
          {title}{count !== undefined ? ` (${count})` : \'\'}
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-nc-text-dim">{right}</span>
          <svg
            className={clsx(\'w-3 h-3 text-nc-text-dim transition-transform duration-200\', open && \'rotate-180\')}
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
    connected: \'bg-nc-green\',
    mocked: \'bg-nc-yellow\',
    error: \'bg-nc-red\',
    unconfigured: \'bg-nc-text-dim/40\',
  };
  return <div className={clsx(\'w-2 h-2 rounded-full shrink-0\', color[status])} />;
}

function formatAge(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return \'just now\';
  if (seconds < 60) return `${seconds}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

function formatDomainLabel(domain: string): string {
  return domain.replace(/_/g, \' \').replace(/\\b\\w/g, (c) => c.toUpperCase());
}
''')


# ═══════════════════════════════════════════════════════════════════
# FIX 3: Bridge test counts — count embedded tests
# ═══════════════════════════════════════════════════════════════════

agg_path = f"{BACKEND}/state_aggregator.py"
with open(agg_path) as f:
    agg = f.read()

# Replace the _count_bridge_tests method to also check embedded tests
old_method = '''    def _count_bridge_tests(self, bridge_file: Path) -> int:
        """Count test functions in a bridge's corresponding test file."""
        tests_dir = settings.repo_root / "tests"
        test_file = tests_dir / f"test_{bridge_file.name}"
        if not test_file.exists():
            # Try alternative naming
            test_file = tests_dir / f"test_{bridge_file.stem}.py"
        if not test_file.exists():
            return 0
        try:
            content = test_file.read_text()
            return len(re.findall(r"def test_", content))
        except Exception:
            return 0'''

new_method = '''    def _count_bridge_tests(self, bridge_file: Path) -> int:
        """Count test functions for a bridge.

        Checks three locations:
          1. Separate test file: tests/test_<bridge>.py
          2. Embedded tests in the bridge file itself (def test_*)
          3. Embedded test count in bridge docstring/comments
        """
        count = 0

        # Check separate test file first
        tests_dir = settings.repo_root / "tests"
        for name in [f"test_{bridge_file.name}", f"test_{bridge_file.stem}.py"]:
            test_file = tests_dir / name
            if test_file.exists():
                try:
                    content = test_file.read_text()
                    count = len(re.findall(r"def test_", content))
                    if count > 0:
                        return count
                except Exception:
                    pass

        # Check embedded tests in bridge file itself
        try:
            content = bridge_file.read_text()
            embedded = len(re.findall(r"def test_", content))
            if embedded > 0:
                return embedded

            # Check for test count in comments like "# Tests: 22/22"
            match = re.search(r"#\\s*Tests?:\\s*(\\d+)", content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

        return count'''

if old_method in agg:
    agg = agg.replace(old_method, new_method)
    with open(agg_path, "w") as f:
        f.write(agg)
    print(f"  [{fixes + 1}] {agg_path} (bridge test counter)")
    fixes += 1
else:
    print(f"  SKIP: bridge test counter (method not found or already patched)")


# ═══════════════════════════════════════════════════════════════════
# FIX 4: page.tsx — clean, no unicode escapes
# ═══════════════════════════════════════════════════════════════════

write(f"{BASE}/app/page.tsx", '''\'use client\';

import { useState } from \'react\';
import type { TabId } from \'@/lib/types\';
import { Sidebar } from \'@/components/Sidebar\';
import { HomeTab } from \'@/components/HomeTab\';
import { useWebSocket } from \'@/hooks/useWebSocket\';

export default function CommandCenter() {
  const [activeTab, setActiveTab] = useState<TabId>(\'home\');
  const { state, status, lastUpdate, refresh } = useWebSocket();

  return (
    <div className="h-screen flex overflow-hidden bg-nc-bg">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        connectionStatus={status}
      />

      <main className="flex-1 overflow-hidden">
        {activeTab === \'home\' && (
          <HomeTab
            state={state}
            connectionStatus={status}
            lastUpdate={lastUpdate}
            onRefresh={refresh}
          />
        )}

        {activeTab !== \'home\' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-sm text-nc-text-dim">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} \u2014 Coming in CC-{getPhase(activeTab)}
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
    home: \'1\', communications: \'3\', agents: \'4\', skills: \'5\',
    operations: \'6\', finance: \'6\', projects: \'7\', clients: \'8\',
    approvals: \'9\', intelligence: \'9\', settings: \'10\', playground: \'10\',
  };
  return phases[tab] || \'?\';
}
''')


print(f"\n{fixes} files fixed. Refresh http://localhost:3000")
print("Backend will auto-reload for bridge test counts.")
