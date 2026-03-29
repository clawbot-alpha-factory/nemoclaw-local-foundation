'use client';

import BrainSidebar from '../components/BrainSidebar';
import CommsTab from '../components/CommsTab';
import AgentsTab from '../components/AgentsTab';
import SkillsTab from '../components/SkillsTab';
import OpsTab from '../components/OpsTab';

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

        {activeTab === 'communications' && (
          <CommsTab />
        )}

        {activeTab === 'agents' && (
          <AgentsTab />
        )}
          {activeTab === 'skills' && <SkillsTab />}

        {activeTab !== 'home' && activeTab !== 'communications' && activeTab !== 'agents' && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-sm text-nc-text-dim">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
          {activeTab === 'operations' && <OpsTab />}
          {activeTab === 'operations' && <OpsTab />}
          {activeTab === 'operations' && <OpsTab />}
          {activeTab === 'operations' && <OpsTab />}
          {activeTab === 'operations' && <OpsTab />}
          {activeTab === 'operations' && <OpsTab />} — Coming in CC-{getPhase(activeTab)}
              </div>
            </div>
          </div>
        )}
      </main>
        <BrainSidebar />
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
