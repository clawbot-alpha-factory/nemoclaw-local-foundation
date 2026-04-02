'use client';

import { useState, useEffect } from 'react';
import { fetchDebates, fetchDebate } from '@/lib/protocol-api';
import type { DebateSession, DebateRound } from '@/lib/protocol-types';

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-blue-500/20 text-blue-400',
    completed: 'bg-emerald-500/20 text-emerald-400',
    cancelled: 'bg-zinc-500/20 text-zinc-400',
  };
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${colors[status] || 'bg-zinc-500/20 text-zinc-400'}`}>
      {status}
    </span>
  );
}

function RoundCard({ round, isAgentA }: { round: DebateRound; isAgentA: boolean }) {
  return (
    <div className={`flex ${isAgentA ? 'justify-start' : 'justify-end'} mb-3`}>
      <div className={`max-w-[80%] rounded-xl p-3 ${
        isAgentA
          ? 'bg-blue-600/10 border border-blue-500/20 rounded-bl-md'
          : 'bg-purple-600/10 border border-purple-500/20 rounded-br-md'
      }`}>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs font-semibold ${isAgentA ? 'text-blue-400' : 'text-purple-400'}`}>
            {round.agent_name}
          </span>
          <span className="text-[10px] text-zinc-500">Round {round.round}</span>
        </div>
        <p className="text-sm text-zinc-200 whitespace-pre-wrap">{round.position}</p>
        {round.evidence.length > 0 && (
          <div className="mt-2 space-y-1">
            {round.evidence.map((e, i) => (
              <div key={i} className="text-[10px] text-zinc-400 bg-zinc-800/50 px-2 py-1 rounded">
                📎 {e}
              </div>
            ))}
          </div>
        )}
        <div className="text-[10px] text-zinc-500 text-right mt-1">
          {new Date(round.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

interface DebateDetailProps {
  debate: DebateSession;
}

function DebateDetail({ debate }: DebateDetailProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-700/50">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-200">{debate.topic}</h3>
          <StatusBadge status={debate.status} />
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-400">
          <span className="text-blue-400">{debate.agent_a_name}</span>
          <span>vs</span>
          <span className="text-purple-400">{debate.agent_b_name}</span>
          <span>&middot;</span>
          <span>{debate.rounds.length}/{debate.max_rounds} rounds</span>
        </div>
      </div>

      {/* Rounds */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {debate.rounds.map((round) => (
          <RoundCard
            key={`${round.round}-${round.agent}`}
            round={round}
            isAgentA={round.agent === debate.agent_a}
          />
        ))}

        {/* Outcome */}
        {debate.outcome && (
          <div className="mt-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg p-3">
            <div className="text-xs font-semibold text-emerald-400 mb-1">Outcome</div>
            <p className="text-sm text-zinc-200">{debate.outcome}</p>
            {debate.ruling_agent && (
              <div className="text-[10px] text-zinc-400 mt-1">Ruling by: {debate.ruling_agent}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface DebateViewProps {
  onStartDebate: () => void;
}

export default function DebateView({ onStartDebate }: DebateViewProps) {
  const [debates, setDebates] = useState<DebateSession[]>([]);
  const [selected, setSelected] = useState<DebateSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDebates()
      .then(({ debates: d }) => setDebates(d))
      .catch(() => setDebates([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading debates...</div>;
  }

  if (selected) {
    return (
      <div className="flex flex-col h-full">
        <button
          onClick={() => setSelected(null)}
          className="px-4 py-2 text-xs text-zinc-400 hover:text-zinc-200 text-left border-b border-zinc-700/50"
        >&larr; Back to debates</button>
        <div className="flex-1 overflow-hidden">
          <DebateDetail debate={selected} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-zinc-700/50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Debates</h2>
        <button
          onClick={onStartDebate}
          className="px-2.5 py-1 text-xs bg-blue-600/20 text-blue-400 rounded-lg hover:bg-blue-600/30 transition-colors"
        >+ New Debate</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {debates.map((d) => (
          <button
            key={d.id}
            onClick={() => setSelected(d)}
            className="w-full text-left px-4 py-3 border-b border-zinc-700/30 hover:bg-zinc-800/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-zinc-200 truncate">{d.topic}</span>
              <StatusBadge status={d.status} />
            </div>
            <div className="text-xs text-zinc-400">
              {d.agent_a_name} vs {d.agent_b_name} &middot; {d.rounds.length} rounds
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">
              {new Date(d.started_at).toLocaleString()}
            </div>
          </button>
        ))}
        {debates.length === 0 && (
          <div className="text-center py-12 text-sm text-zinc-500">
            No debates yet. Start one to see agents challenge each other.
          </div>
        )}
      </div>
    </div>
  );
}
