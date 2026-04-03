'use client';

import { useState, useCallback } from 'react';
import type { Lane, CommsMessage } from '@/lib/comms-types';
import type { ConversationType } from '@/lib/store';
import LaneList from './LaneList';
import ChatThread from './ChatThread';
import { ErrorBoundary } from './ErrorBoundary';
import ConversationTypeSelector from './comms/ConversationTypeSelector';
import DebateView from './comms/DebateView';
import BrainstormView from './comms/BrainstormView';
import ProtocolInbox from './comms/ProtocolInbox';
import StartDebateModal from './comms/StartDebateModal';
import StartBrainstormModal from './comms/StartBrainstormModal';
import { sendMessage } from '@/lib/comms-api';

export default function CommsTab() {
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [activeLaneId, setActiveLaneId] = useState<string | null>(null);
  const [conversationType, setConversationType] = useState<ConversationType>('dm');
  const [showStartDebate, setShowStartDebate] = useState(false);
  const [showStartBrainstorm, setShowStartBrainstorm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showQuickTask, setShowQuickTask] = useState(false);
  const [quickTaskText, setQuickTaskText] = useState('');
  const [quickTaskSending, setQuickTaskSending] = useState(false);

  const activeLane = lanes.find((l) => l.id === activeLaneId) || null;

  const handleLanesLoaded = useCallback((loadedLanes: Lane[]) => {
    setLanes(loadedLanes);
  }, []);

  const handleSelectLane = useCallback((laneId: string) => {
    setActiveLaneId(laneId);
  }, []);

  const handleNewMessage = useCallback((msg: CommsMessage) => {
    setLanes((prev) =>
      prev.map((lane) => {
        if (lane.id === msg.lane_id) {
          return { ...lane, last_message: msg };
        }
        return lane;
      })
    );
  }, []);

  const handleConversationTypeChange = (type: ConversationType) => {
    setConversationType(type);
    setActiveLaneId(null);
  };

  // Filter lanes for group view
  const groupLanes = lanes.filter(l => l.lane_type === 'group' || l.lane_type === 'broadcast');

  // Render the right panel based on conversation type
  function renderRightPanel() {
    switch (conversationType) {
      case 'debate':
        return (
          <DebateView
            key={refreshKey}
            onStartDebate={() => setShowStartDebate(true)}
          />
        );
      case 'brainstorm':
        return (
          <BrainstormView
            key={refreshKey}
            onStartSession={() => setShowStartBrainstorm(true)}
          />
        );
      case 'agent-channel':
        return <ProtocolInbox key={refreshKey} />;
      case 'dm':
      case 'group':
      default:
        if (activeLane) {
          return <ChatThread lane={activeLane} onNewMessage={handleNewMessage} />;
        }
        return (
          <div className="flex flex-col items-center justify-center h-full text-nc-text-dim">
            <div className="text-5xl mb-4">💬</div>
            <h3 className="text-lg font-medium text-nc-text-dim">
              {conversationType === 'group' ? 'Group Channels' : 'Team Chat'}
            </h3>
            <p className="text-sm text-nc-text-muted mt-1">
              Select a conversation to get started
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3 text-xs text-nc-text-dim">
              <div className="flex items-center gap-2 bg-nc-surface-2 px-3 py-2 rounded-lg">
                <span>🤖</span>
                <span>DM any agent directly</span>
              </div>
              <div className="flex items-center gap-2 bg-nc-surface-2 px-3 py-2 rounded-lg">
                <span>📢</span>
                <span>All Hands broadcast</span>
              </div>
              <div className="flex items-center gap-2 bg-nc-surface-2 px-3 py-2 rounded-lg">
                <span>⚔️</span>
                <span>Watch agent debates</span>
              </div>
              <div className="flex items-center gap-2 bg-nc-surface-2 px-3 py-2 rounded-lg">
                <span>💡</span>
                <span>See brainstorm sessions</span>
              </div>
            </div>
          </div>
        );
    }
  }

  // Should we show the lane list?
  const showLaneList = conversationType === 'dm' || conversationType === 'group';

  const handleQuickTask = async () => {
    if (!quickTaskText.trim() || !activeLaneId || quickTaskSending) return;
    setQuickTaskSending(true);
    try {
      await sendMessage(activeLaneId, quickTaskText.trim(), 'task');
      setQuickTaskText('');
      setShowQuickTask(false);
    } catch (e) {
      console.error('Quick task failed:', e);
    } finally {
      setQuickTaskSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-nc-bg overflow-hidden">
      {/* Conversation type selector + Quick Task */}
      <div className="flex items-center">
        <div className="flex-1">
          <ConversationTypeSelector active={conversationType} onChange={handleConversationTypeChange} />
        </div>
        {activeLaneId && (
          <button
            onClick={() => setShowQuickTask(!showQuickTask)}
            className="mr-3 px-2.5 py-1.5 text-xs rounded-lg bg-amber-600/20 text-amber-400 hover:bg-amber-600/30 transition-colors"
            title="Quick Task"
          >
            📋 Quick Task
          </button>
        )}
      </div>

      {/* Quick Task inline form */}
      {showQuickTask && activeLaneId && (
        <div className="px-4 py-2 border-b border-nc-border flex gap-2 items-center bg-nc-surface">
          <input
            type="text"
            value={quickTaskText}
            onChange={(e) => setQuickTaskText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleQuickTask(); }}
            placeholder="Describe the task..."
            className="flex-1 bg-nc-surface-2 text-nc-text text-xs px-3 py-2 rounded-lg border border-nc-border focus:border-nc-accent focus:outline-none placeholder:text-nc-text-muted"
            autoFocus
          />
          <button
            onClick={handleQuickTask}
            disabled={!quickTaskText.trim() || quickTaskSending}
            className="text-xs px-3 py-2 rounded-lg bg-amber-600/80 hover:bg-amber-500/80 text-white font-medium transition-colors disabled:opacity-50"
          >
            {quickTaskSending ? '...' : 'Send'}
          </button>
          <button
            onClick={() => setShowQuickTask(false)}
            className="text-xs text-nc-text-muted hover:text-nc-text-dim px-1"
          >
            ✕
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* Lane list — left panel (only for DM/Group views) */}
        {showLaneList && (
          <div className="w-72 flex-shrink-0 border-r border-nc-border bg-nc-surface">
            <LaneList
              activeLaneId={activeLaneId}
              onSelectLane={handleSelectLane}
              lanes={conversationType === 'group' ? groupLanes : lanes}
              onLanesLoaded={handleLanesLoaded}
            />
          </div>
        )}

        {/* Right panel */}
        <div className="flex-1 min-w-0">
          {renderRightPanel()}
        </div>
      </div>

      {/* Modals */}
      {showStartDebate && (
        <StartDebateModal
          onClose={() => setShowStartDebate(false)}
          onCreated={() => {
            setShowStartDebate(false);
            setRefreshKey(k => k + 1);
          }}
        />
      )}
      {showStartBrainstorm && (
        <StartBrainstormModal
          onClose={() => setShowStartBrainstorm(false)}
          onCreated={() => {
            setShowStartBrainstorm(false);
            setRefreshKey(k => k + 1);
          }}
        />
      )}
    </div>
  );
}
