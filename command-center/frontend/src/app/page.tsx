'use client';

import BrainSidebar from '../components/BrainSidebar';
import CommsTab from '../components/CommsTab';
import AgentsTab from '../components/AgentsTab';
import SkillsTab from '../components/SkillsTab';
import ApprovalsTab from '../components/ApprovalsTab';
import ClientsTab from '../components/ClientsTab';
import ProjectsTab from '../components/ProjectsTab';
import OpsTab from '../components/OpsTab';
import ExecutionTab from '../components/ExecutionTab';

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
        {activeTab === 'communications' && <CommsTab />}
        {activeTab === 'agents' && <AgentsTab />}
        {activeTab === 'skills' && <SkillsTab />}
        {activeTab === 'operations' && <OpsTab />}
        {activeTab === 'execution' && <ExecutionTab />}
        {activeTab === 'approvals' && <ApprovalsTab />}
        {activeTab === 'clients' && <ClientsTab />}
        {activeTab === 'projects' && <ProjectsTab />}

        {!['home', 'communications', 'agents', 'skills', 'operations',
           'execution', 'approvals', 'clients', 'projects'].includes(activeTab) && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-sm text-nc-text-dim">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} — Coming Soon
              </div>
            </div>
          </div>
        )}
      </main>
      <BrainSidebar />
    </div>
  );
}
