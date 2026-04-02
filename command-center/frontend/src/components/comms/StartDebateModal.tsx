'use client';

import { useState, useEffect } from 'react';
import { startDebate } from '@/lib/protocol-api';
import { fetchAgentProfiles } from '@/lib/agents-api';
import type { AgentProfile } from '@/lib/agents-api';

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function StartDebateModal({ onClose, onCreated }: Props) {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [topic, setTopic] = useState('');
  const [agentA, setAgentA] = useState('');
  const [agentB, setAgentB] = useState('');
  const [maxRounds, setMaxRounds] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAgentProfiles()
      .then(({ agents: a }) => setAgents(a))
      .catch(console.error);
  }, []);

  async function handleSubmit() {
    if (!topic.trim() || !agentA || !agentB || agentA === agentB) {
      setError('Select two different agents and a topic');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await startDebate({ topic: topic.trim(), agent_a: agentA, agent_b: agentB, max_rounds: maxRounds });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start debate');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-800 border border-zinc-700 rounded-xl p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-zinc-200 mb-4">Start New Debate</h2>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Topic</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="What should agents debate?"
              className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:border-blue-500/50 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Proposer</label>
              <select
                value={agentA}
                onChange={(e) => setAgentA(e.target.value)}
                className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:outline-none"
              >
                <option value="">Select agent...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Opponent</label>
              <select
                value={agentB}
                onChange={(e) => setAgentB(e.target.value)}
                className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:outline-none"
              >
                <option value="">Select agent...</option>
                {agents.filter(a => a.id !== agentA).map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs text-zinc-400 block mb-1">Max Rounds</label>
            <input
              type="number"
              value={maxRounds}
              onChange={(e) => setMaxRounds(Number(e.target.value))}
              min={1}
              max={10}
              className="w-24 bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:outline-none"
            />
          </div>

          {error && <div className="text-xs text-red-400">{error}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >Cancel</button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:opacity-50 transition-colors"
            >{submitting ? 'Starting...' : 'Start Debate'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
