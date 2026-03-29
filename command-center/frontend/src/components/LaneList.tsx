'use client';

import { useEffect, useState } from 'react';
import type { Lane } from '@/lib/comms-types';
import { fetchLanes } from '@/lib/comms-api';

interface LaneListProps {
  activeLaneId: string | null;
  onSelectLane: (laneId: string) => void;
  lanes: Lane[];
  onLanesLoaded: (lanes: Lane[]) => void;
}

const LANE_TYPE_LABELS: Record<string, string> = {
  dm: 'Direct Messages',
  broadcast: 'Channels',
  system: 'System',
};

function laneTypeOrder(type: string): number {
  if (type === 'dm') return 0;
  if (type === 'broadcast' || type === 'group') return 1;
  if (type === 'system') return 2;
  return 3;
}

function formatTime(ts: string | null): string {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'now';
  if (diffMins < 60) return `${diffMins}m`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '...' : text;
}

export default function LaneList({
  activeLaneId,
  onSelectLane,
  lanes,
  onLanesLoaded,
}: LaneListProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const fetched = await fetchLanes();
        if (mounted) {
          onLanesLoaded(fetched);
          setLoading(false);
        }
      } catch (e) {
        if (mounted) {
          setError(e instanceof Error ? e.message : 'Failed to load lanes');
          setLoading(false);
        }
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Loading lanes...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-400 text-sm">
        {error}
      </div>
    );
  }

  // Group lanes by type
  const grouped: Record<string, Lane[]> = {};
  for (const lane of lanes) {
    const group = lane.lane_type === 'group' ? 'broadcast' : lane.lane_type;
    if (!grouped[group]) grouped[group] = [];
    grouped[group].push(lane);
  }

  const sortedGroups = Object.entries(grouped).sort(
    ([a], [b]) => laneTypeOrder(a) - laneTypeOrder(b)
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-700/50">
        <h2 className="text-sm font-semibold text-zinc-200 tracking-wide uppercase">
          Team Chat
        </h2>
      </div>

      {/* Lane groups */}
      <div className="flex-1 overflow-y-auto">
        {sortedGroups.map(([groupType, groupLanes]) => (
          <div key={groupType}>
            <div className="px-4 py-2 text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
              {LANE_TYPE_LABELS[groupType] || groupType}
            </div>
            {groupLanes.map((lane) => (
              <button
                key={lane.id}
                onClick={() => onSelectLane(lane.id)}
                className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors ${
                  activeLaneId === lane.id
                    ? 'bg-zinc-700/50 border-l-2 border-blue-500'
                    : 'hover:bg-zinc-800/50 border-l-2 border-transparent'
                }`}
              >
                {/* Avatar */}
                <span className="text-xl mt-0.5 flex-shrink-0">
                  {lane.avatar || '💬'}
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-sm font-medium truncate ${
                        activeLaneId === lane.id ? 'text-white' : 'text-zinc-300'
                      }`}
                    >
                      {lane.name}
                    </span>
                    {lane.last_message && (
                      <span className="text-[11px] text-zinc-500 flex-shrink-0 ml-2">
                        {formatTime(lane.last_message.timestamp)}
                      </span>
                    )}
                  </div>
                  {lane.last_message ? (
                    <p className="text-xs text-zinc-500 truncate mt-0.5">
                      {lane.last_message.sender_type === 'user'
                        ? 'You: '
                        : `${lane.last_message.sender_name}: `}
                      {truncate(lane.last_message.content, 45)}
                    </p>
                  ) : (
                    <p className="text-xs text-zinc-600 italic mt-0.5">
                      No messages yet
                    </p>
                  )}
                </div>

                {/* Unread badge */}
                {lane.unread_count > 0 && (
                  <span className="flex-shrink-0 bg-blue-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center mt-1">
                    {lane.unread_count > 9 ? '9+' : lane.unread_count}
                  </span>
                )}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
