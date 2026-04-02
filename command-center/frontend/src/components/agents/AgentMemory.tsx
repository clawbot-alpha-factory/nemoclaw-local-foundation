'use client';

import { useState, useEffect } from 'react';
import { fetchAgentMemory } from '@/lib/agents-api';
import type { AgentMemoryEntry } from '@/lib/agents-api';

interface Props {
  agentId: string;
}

export default function AgentMemory({ agentId }: Props) {
  const [entries, setEntries] = useState<AgentMemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchAgentMemory(agentId)
      .then(({ lessons }) => setEntries(lessons))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className="text-sm text-zinc-500 animate-pulse p-4">Loading memory...</div>;

  const filtered = search
    ? entries.filter(e =>
        e.key.toLowerCase().includes(search.toLowerCase()) ||
        String(e.value).toLowerCase().includes(search.toLowerCase())
      )
    : entries;

  return (
    <div className="p-4 space-y-3">
      {/* Search */}
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search memory..."
        className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:border-blue-500/50 focus:outline-none"
      />

      {/* Entries */}
      <div className="space-y-2">
        {filtered.map((entry, i) => (
          <div key={i} className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-blue-400">{entry.key}</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-zinc-500 capitalize">{entry.memory_type}</span>
                <span className="text-[10px] text-zinc-500">imp: {entry.importance}</span>
              </div>
            </div>
            <div className="text-sm text-zinc-200 whitespace-pre-wrap">
              {typeof entry.value === 'string' ? entry.value : JSON.stringify(entry.value, null, 2)}
            </div>
            <div className="text-[10px] text-zinc-500 mt-1">
              {entry.source} &middot; {new Date(entry.timestamp).toLocaleString()}
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-8 text-sm text-zinc-500">
            {search ? 'No matching entries' : 'No memory entries'}
          </div>
        )}
      </div>
    </div>
  );
}
