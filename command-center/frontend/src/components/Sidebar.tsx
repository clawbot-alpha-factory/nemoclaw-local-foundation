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
  { id: 'home', label: 'Home', emoji: '⌂' },
  { id: 'communications', label: 'Comms', emoji: '💬', disabled: false },
  { id: 'agents', label: 'Agents', emoji: '🤖', disabled: false },
  { id: 'skills', label: 'Skills', emoji: '⚡', disabled: false },
  { id: 'operations', label: 'Ops', emoji: '📊', disabled: false },
  { id: 'finance', label: 'Finance', emoji: '💰', disabled: false },
  { id: 'projects', label: 'Projects', emoji: '📋', disabled: false },
  { id: 'clients', label: 'Clients', emoji: '🏢', disabled: false },
  { id: 'approvals', label: 'Approvals', emoji: '✅', disabled: false },
  { id: 'intelligence', label: 'Intel', emoji: '🧠', disabled: false },
  { id: 'settings', label: 'Settings', emoji: '⚙', disabled: false },
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
