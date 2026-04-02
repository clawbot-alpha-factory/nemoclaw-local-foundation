'use client';

import { useState, useEffect } from 'react';
import { fetchProtocolHistory, fetchDebates, fetchSessions } from '@/lib/protocol-api';
import type { ProtocolMessage, DebateSession, InteractionSession } from '@/lib/protocol-types';

interface Props {
  agentId: string;
}

export default function AgentDebates({ agentId }: Props) {
  const [debates, setDebates] = useState<DebateSession[]>([]);
  const [sessions, setSessions] = useState<InteractionSession[]>([]);
  const [recentMessages, setRecentMessages] = useState<ProtocolMessage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchDebates().catch(() => ({ debates: [] })),
      fetchSessions().catch(() => ({ sessions: [] })),
      fetchProtocolHistory(50).catch(() => ({ messages: [] })),
    ]).then(([debRes, sessRes, msgRes]) => {
      setDebates(debRes.debates.filter(d => d.agent_a === agentId || d.agent_b === agentId));
      setSessions(sessRes.sessions.filter(s => s.participants.includes(agentId)));
      setRecentMessages(msgRes.messages.filter(m => m.sender === agentId));
    }).finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className="text-sm text-zinc-500 animate-pulse p-4">Loading interactions...</div>;

  return (
    <div className="p-4 space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30 text-center">
          <div className="text-xl font-bold text-zinc-200">{debates.length}</div>
          <div className="text-[10px] text-zinc-400">Debates</div>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30 text-center">
          <div className="text-xl font-bold text-zinc-200">{sessions.length}</div>
          <div className="text-[10px] text-zinc-400">Sessions</div>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30 text-center">
          <div className="text-xl font-bold text-zinc-200">{recentMessages.length}</div>
          <div className="text-[10px] text-zinc-400">Recent Messages</div>
        </div>
      </div>

      {/* Debates */}
      {debates.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Debates</h4>
          <div className="space-y-1">
            {debates.map((d) => (
              <div key={d.id} className="bg-zinc-800/30 rounded-lg p-3 border border-zinc-700/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-200">{d.topic}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    d.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>{d.status}</span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">
                  vs {d.agent_a === agentId ? d.agent_b_name : d.agent_a_name} &middot; {d.rounds.length} rounds
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sessions */}
      {sessions.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Sessions</h4>
          <div className="space-y-1">
            {sessions.map((s) => (
              <div key={s.session_id} className="bg-zinc-800/30 rounded-lg p-3 border border-zinc-700/30">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-200">{s.topic}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">{s.mode}</span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">
                  {s.participant_names.join(', ')} &middot; {s.contributions.length} contributions
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent protocol messages */}
      {recentMessages.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Recent Protocol Messages</h4>
          <div className="space-y-1">
            {recentMessages.slice(0, 10).map((m) => (
              <div key={m.id} className="bg-zinc-800/30 rounded-lg p-2 border border-zinc-700/30 text-xs">
                <span className="text-blue-400 font-medium">{m.intent}</span>
                <span className="text-zinc-400"> &rarr; {m.recipients.join(', ') || m.channel_id}</span>
                <div className="text-zinc-300 mt-0.5 truncate">{m.content}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {debates.length === 0 && sessions.length === 0 && recentMessages.length === 0 && (
        <div className="text-center py-8 text-sm text-zinc-500">No interactions found for this agent</div>
      )}
    </div>
  );
}
