'use client';

import { useState, useCallback } from 'react';
import type { Lane, CommsMessage } from '@/lib/comms-types';
import type { ConversationType } from '@/lib/store';
import LaneList from './LaneList';
import ChatThread from './ChatThread';
import ConversationTypeSelector from './comms/ConversationTypeSelector';
import DebateView from './comms/DebateView';
import BrainstormView from './comms/BrainstormView';
import ProtocolInbox from './comms/ProtocolInbox';
import StartDebateModal from './comms/StartDebateModal';
import StartBrainstormModal from './comms/StartBrainstormModal';

export default function CommsTab() {
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [activeLaneId, setActiveLaneId] = useState<string | null>(null);
  const [conversationType, setConversationType] = useState<ConversationType>('dm');
  const [showStartDebate, setShowStartDebate] = useState(false);
  const [showStartBrainstorm, setShowStartBrainstorm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

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
          <div className="flex flex-col items-center justify-center h-full text-zinc-500">
            <div className="text-5xl mb-4">💬</div>
            <h3 className="text-lg font-medium text-zinc-400">
              {conversationType === 'group' ? 'Group Channels' : 'Team Chat'}
            </h3>
            <p className="text-sm text-zinc-600 mt-1">
              Select a conversation to get started
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3 text-xs text-zinc-500">
              <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg">
                <span>🤖</span>
                <span>DM any agent directly</span>
              </div>
              <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg">
                <span>📢</span>
                <span>All Hands broadcast</span>
              </div>
              <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg">
                <span>⚔️</span>
                <span>Watch agent debates</span>
              </div>
              <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg">
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

  return (
    <div className="flex flex-col h-full bg-zinc-900 rounded-xl overflow-hidden border border-zinc-700/50">
      {/* Conversation type selector */}
      <ConversationTypeSelector active={conversationType} onChange={handleConversationTypeChange} />

      <div className="flex flex-1 min-h-0">
        {/* Lane list — left panel (only for DM/Group views) */}
        {showLaneList && (
          <div className="w-72 flex-shrink-0 border-r border-zinc-700/50 bg-zinc-900/80">
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
