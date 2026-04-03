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
import FinanceTab from '../components/FinanceTab';
import IntelligenceTab from '../components/IntelligenceTab';
import ResearchTab from '../components/ResearchTab';
import SettingsTab from '../components/SettingsTab';
import MarketingTab from '../components/MarketingTab';
import WorkReviewTab from '../components/WorkReviewTab';
import ControlPanelTab from '../components/ControlPanelTab';

import { useState } from 'react';
import type { TabId } from '@/lib/types';
import { Sidebar } from '@/components/Sidebar';
import { HomeTab } from '@/components/HomeTab';
import { ErrorBoundary } from '@/components/ErrorBoundary';
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
          <ErrorBoundary fallbackLabel="Home failed to load">
            <HomeTab
              state={state}
              connectionStatus={status}
              lastUpdate={lastUpdate}
              onRefresh={refresh}
            />
          </ErrorBoundary>
        )}
        {activeTab === 'communications' && <ErrorBoundary fallbackLabel="Communications failed to load"><CommsTab /></ErrorBoundary>}
        {activeTab === 'agents' && <ErrorBoundary fallbackLabel="Agents failed to load"><AgentsTab /></ErrorBoundary>}
        {activeTab === 'skills' && <ErrorBoundary fallbackLabel="Skills failed to load"><SkillsTab /></ErrorBoundary>}
        {activeTab === 'operations' && <ErrorBoundary fallbackLabel="Operations failed to load"><OpsTab /></ErrorBoundary>}
        {activeTab === 'execution' && <ErrorBoundary fallbackLabel="Execution failed to load"><ExecutionTab /></ErrorBoundary>}
        {activeTab === 'approvals' && <ErrorBoundary fallbackLabel="Approvals failed to load"><ApprovalsTab /></ErrorBoundary>}
        {activeTab === 'clients' && <ErrorBoundary fallbackLabel="Clients failed to load"><ClientsTab /></ErrorBoundary>}
        {activeTab === 'projects' && <ErrorBoundary fallbackLabel="Projects failed to load"><ProjectsTab /></ErrorBoundary>}
        {activeTab === 'finance' && <ErrorBoundary fallbackLabel="Finance failed to load"><FinanceTab /></ErrorBoundary>}
        {activeTab === 'intelligence' && <ErrorBoundary fallbackLabel="Intelligence failed to load"><IntelligenceTab /></ErrorBoundary>}
        {activeTab === 'research' && <ErrorBoundary fallbackLabel="Research failed to load"><ResearchTab /></ErrorBoundary>}
        {activeTab === 'settings' && <ErrorBoundary fallbackLabel="Settings failed to load"><SettingsTab /></ErrorBoundary>}
        {activeTab === 'marketing' && <ErrorBoundary fallbackLabel="Marketing failed to load"><MarketingTab /></ErrorBoundary>}

        {!['home', 'communications', 'agents', 'skills', 'operations',
           'execution', 'approvals', 'clients', 'projects',
           'finance', 'intelligence', 'research', 'settings', 'marketing',
           'work-review', 'control'].includes(activeTab) && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-sm text-nc-text-dim">
                {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} — Coming Soon
              </div>
            </div>
          </div>
        )}

        {activeTab === 'work-review' && <ErrorBoundary fallbackLabel="Work Review failed to load"><WorkReviewTab /></ErrorBoundary>}

        {activeTab === 'control' && <ErrorBoundary fallbackLabel="Control Panel failed to load"><ControlPanelTab /></ErrorBoundary>}
      </main>
      <BrainSidebar />
    </div>
  );
}
