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

type NavGroup = NavItem[];

const NAV_GROUPS: NavGroup[] = [
  // Group 1: Home
  [
    { id: 'home', label: 'Home', emoji: '🏠' },
  ],
  // Group 2: Comms + Agents + Skills
  [
    { id: 'communications', label: 'Chat', emoji: '💬' },
    { id: 'agents', label: 'Team', emoji: '🤖' },
    { id: 'skills', label: 'Skills', emoji: '⚡' },
  ],
  // Group 3: Ops + Engine + Approvals
  [
    { id: 'operations', label: 'Ops', emoji: '📊' },
    { id: 'execution', label: 'Engine', emoji: '🚀' },
    { id: 'approvals', label: 'Approve', emoji: '✅' },
  ],
  // Group 4: Projects + Work Review + Clients
  [
    { id: 'projects', label: 'Projects', emoji: '📋' },
    { id: 'work-review', label: 'Review', emoji: '📝' },
    { id: 'clients', label: 'Clients', emoji: '🏢' },
  ],
  // Group 5: Finance + Intel + Research + Marketing
  [
    { id: 'finance', label: 'Finance', emoji: '💰' },
    { id: 'intelligence', label: 'Intel', emoji: '🧠' },
    { id: 'research', label: 'Research', emoji: '🔍' },
    { id: 'marketing', label: 'Marketing', emoji: '🎬' },
  ],
  // Group 6: Control + Settings
  [
    { id: 'control', label: 'Control', emoji: '🎛' },
    { id: 'settings', label: 'Settings', emoji: '⚙' },
  ],
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

  const statusLabel = {
    connected: 'Online',
    connecting: 'Connecting',
    disconnected: 'Offline',
    error: 'Error',
  }[connectionStatus];

  return (
    <aside className="w-20 bg-nc-surface border-r border-nc-border flex flex-col items-center py-4 shrink-0">
      {/* Logo */}
      <div className="mb-4 flex flex-col items-center">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-nc-accent to-nc-accent-dim flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-nc-accent/20">
          NC
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col flex-1 w-full px-2 overflow-y-auto overflow-x-hidden">
        {NAV_GROUPS.map((group, gi) => (
          <div key={gi}>
            {gi > 0 && (
              <div className="mx-3 my-1.5 border-t border-nc-border" />
            )}
            <div className="flex flex-col gap-0.5">
              {group.map((item) => (
                <button
                  key={item.id}
                  onClick={() => !item.disabled && onTabChange(item.id)}
                  disabled={item.disabled}
                  title={item.label}
                  className={clsx(
                    'w-full rounded-lg flex flex-col items-center justify-center py-2 text-xs transition-colors relative',
                    activeTab === item.id
                      ? 'bg-nc-accent/10 text-nc-accent border-l-2 border-nc-accent'
                      : item.disabled
                      ? 'text-nc-text-muted cursor-not-allowed'
                      : 'text-nc-text-dim hover:bg-nc-surface-2 hover:text-nc-text'
                  )}
                >
                  <span className="text-base leading-none">{item.emoji}</span>
                  <span className="text-[9px] leading-none mt-1 truncate w-full text-center">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Connection status */}
      <div className="mt-2 flex flex-col items-center gap-1 pt-2 border-t border-nc-border w-full px-2">
        <div className={clsx('w-2 h-2 rounded-full', statusColor)} />
        <span className="text-[9px] text-nc-text-muted">{statusLabel}</span>
      </div>
    </aside>
  );
}
