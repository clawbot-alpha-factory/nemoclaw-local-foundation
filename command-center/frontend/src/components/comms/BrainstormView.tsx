'use client';

import { useState, useEffect } from 'react';
import { fetchSessions, fetchSession } from '@/lib/protocol-api';
import type { InteractionSession, BrainstormContribution, InteractionMode } from '@/lib/protocol-types';

const MODE_COLORS: Record<InteractionMode, string> = {
  brainstorm: 'bg-amber-500/20 text-amber-400',
  critique: 'bg-red-500/20 text-red-400',
  debate: 'bg-purple-500/20 text-purple-400',
  synthesis: 'bg-blue-500/20 text-blue-400',
  reflection: 'bg-emerald-500/20 text-emerald-400',
};

const MODE_ICONS: Record<InteractionMode, string> = {
  brainstorm: '💡',
  critique: '🔍',
  debate: '⚔️',
  synthesis: '🔗',
  reflection: '🪞',
};

function ModeBadge({ mode }: { mode: InteractionMode }) {
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${MODE_COLORS[mode]}`}>
      {MODE_ICONS[mode]} {mode}
    </span>
  );
}

function ContributionCard({ c }: { c: BrainstormContribution }) {
  return (
    <div className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-xs font-semibold text-blue-400">{c.agent_name}</span>
        <span className="text-[10px] text-zinc-500 capitalize">{c.role}</span>
        <span className="text-[10px] text-zinc-500">R{c.round}</span>
        {c.weight !== 1 && (
          <span className="text-[10px] text-zinc-500">w:{c.weight}</span>
        )}
      </div>
      <p className="text-sm text-zinc-200 whitespace-pre-wrap">{c.content}</p>
      <div className="text-[10px] text-zinc-500 text-right mt-1">
        {new Date(c.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}

function SessionDetail({ session }: { session: InteractionSession }) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-700/50">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-sm font-semibold text-zinc-200">{session.topic}</h3>
          <ModeBadge mode={session.mode} />
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span>{session.participant_names.join(', ')}</span>
          <span>&middot;</span>
          <span>{session.rounds_completed}/{session.max_rounds} rounds</span>
          <span>&middot;</span>
          <span className={session.status === 'complete' ? 'text-emerald-400' : 'text-blue-400'}>
            {session.status}
          </span>
        </div>
      </div>

      {/* Contributions */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {session.contributions.map((c, i) => (
          <ContributionCard key={i} c={c} />
        ))}

        {/* Output */}
        {session.output && Object.keys(session.output).length > 0 && (
          <div className="mt-4 bg-emerald-900/20 border border-emerald-500/20 rounded-lg p-3">
            <div className="text-xs font-semibold text-emerald-400 mb-1">Session Output</div>
            <pre className="text-xs text-zinc-300 whitespace-pre-wrap overflow-x-auto">
              {JSON.stringify(session.output, null, 2)}
            </pre>
          </div>
        )}

        {/* Conflicts */}
        {session.conflicts.length > 0 && (
          <div className="mt-2 bg-red-900/20 border border-red-500/20 rounded-lg p-3">
            <div className="text-xs font-semibold text-red-400 mb-1">Conflicts</div>
            {session.conflicts.map((c, i) => (
              <div key={i} className="text-xs text-zinc-300">&bull; {c}</div>
            ))}
          </div>
        )}

        {/* Lessons */}
        {session.lessons.length > 0 && (
          <div className="mt-2 bg-blue-900/20 border border-blue-500/20 rounded-lg p-3">
            <div className="text-xs font-semibold text-blue-400 mb-1">Lessons Learned</div>
            {session.lessons.map((l, i) => (
              <div key={i} className="text-xs text-zinc-300">&bull; {l}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface BrainstormViewProps {
  onStartSession: () => void;
}

export default function BrainstormView({ onStartSession }: BrainstormViewProps) {
  const [sessions, setSessions] = useState<InteractionSession[]>([]);
  const [selected, setSelected] = useState<InteractionSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSessions()
      .then(({ sessions: s }) => setSessions(s))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-full text-zinc-500 text-sm">Loading sessions...</div>;
  }

  if (selected) {
    return (
      <div className="flex flex-col h-full">
        <button
          onClick={() => setSelected(null)}
          className="px-4 py-2 text-xs text-zinc-400 hover:text-zinc-200 text-left border-b border-zinc-700/50"
        >&larr; Back to sessions</button>
        <div className="flex-1 overflow-hidden">
          <SessionDetail session={selected} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-zinc-700/50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Brainstorms & Sessions</h2>
        <button
          onClick={onStartSession}
          className="px-2.5 py-1 text-xs bg-amber-500/20 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-colors"
        >+ New Session</button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => setSelected(s)}
            className="w-full text-left px-4 py-3 border-b border-zinc-700/30 hover:bg-zinc-800/50 transition-colors"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-zinc-200 truncate">{s.topic}</span>
              <ModeBadge mode={s.mode} />
            </div>
            <div className="text-xs text-zinc-400">
              {s.participant_names.join(', ')} &middot; {s.contributions.length} contributions
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">
              {new Date(s.started_at).toLocaleString()}
            </div>
          </button>
        ))}
        {sessions.length === 0 && (
          <div className="text-center py-12 text-sm text-zinc-500">
            No sessions yet. Start a brainstorm to see agents collaborate.
          </div>
        )}
      </div>
    </div>
  );
}
