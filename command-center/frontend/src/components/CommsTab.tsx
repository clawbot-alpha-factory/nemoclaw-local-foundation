'use client';

import { useState, useCallback } from 'react';
import type { Lane, CommsMessage } from '@/lib/comms-types';
import LaneList from './LaneList';
import ChatThread from './ChatThread';

export default function CommsTab() {
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [activeLaneId, setActiveLaneId] = useState<string | null>(null);

  const activeLane = lanes.find((l) => l.id === activeLaneId) || null;

  const handleLanesLoaded = useCallback((loadedLanes: Lane[]) => {
    setLanes(loadedLanes);
  }, []);

  const handleSelectLane = useCallback((laneId: string) => {
    setActiveLaneId(laneId);
  }, []);

  const handleNewMessage = useCallback((msg: CommsMessage) => {
    // Update lane's last_message in the list for real-time preview
    setLanes((prev) =>
      prev.map((lane) => {
        if (lane.id === msg.lane_id) {
          return { ...lane, last_message: msg };
        }
        return lane;
      })
    );
  }, []);

  return (
    <div className="flex h-full bg-zinc-900 rounded-xl overflow-hidden border border-zinc-700/50">
      {/* Lane list — left panel */}
      <div className="w-72 flex-shrink-0 border-r border-zinc-700/50 bg-zinc-900/80">
        <LaneList
          activeLaneId={activeLaneId}
          onSelectLane={handleSelectLane}
          lanes={lanes}
          onLanesLoaded={handleLanesLoaded}
        />
      </div>

      {/* Conversation view — right panel */}
      <div className="flex-1 min-w-0">
        {activeLane ? (
          <ChatThread lane={activeLane} onNewMessage={handleNewMessage} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500">
            <div className="text-5xl mb-4">💬</div>
            <h3 className="text-lg font-medium text-zinc-400">Team Chat</h3>
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
                <span>📋</span>
                <span>Task & decision messages</span>
              </div>
              <div className="flex items-center gap-2 bg-zinc-800/50 px-3 py-2 rounded-lg">
                <span>✅</span>
                <span>Approval workflows</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
