'use client';

import { useState, useEffect } from 'react';
import { startSession } from '@/lib/protocol-api';
import { fetchAgentProfiles } from '@/lib/agents-api';
import type { AgentProfile } from '@/lib/agents-api';
import type { InteractionMode } from '@/lib/protocol-types';

const MODES: { id: InteractionMode; label: string; icon: string; description: string }[] = [
  { id: 'brainstorm', label: 'Brainstorm', icon: '💡', description: 'Generate ideas freely, no critique' },
  { id: 'critique', label: 'Critique', icon: '🔍', description: 'Evaluate output with scoring' },
  { id: 'synthesis', label: 'Synthesis', icon: '🔗', description: 'Merge viewpoints into unified output' },
  { id: 'reflection', label: 'Reflection', icon: '🪞', description: 'Learn from past decisions' },
];

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function StartBrainstormModal({ onClose, onCreated }: Props) {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState<InteractionMode>('brainstorm');
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [maxRounds, setMaxRounds] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAgentProfiles()
      .then(({ agents: a }) => setAgents(a))
      .catch(console.error);
  }, []);

  function toggleAgent(id: string) {
    setSelectedAgents((prev) =>
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  }

  async function handleSubmit() {
    if (!topic.trim() || selectedAgents.length < 2) {
      setError('Need a topic and at least 2 agents');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await startSession({
        mode,
        topic: topic.trim(),
        participants: selectedAgents,
        max_rounds: maxRounds,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-zinc-800 border border-zinc-700 rounded-xl p-5 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-zinc-200 mb-4">Start Interaction Session</h2>

        <div className="space-y-3">
          {/* Mode selector */}
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Mode</label>
            <div className="grid grid-cols-4 gap-2">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={`text-left p-2 rounded-lg border transition-colors ${
                    mode === m.id
                      ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                      : 'bg-zinc-700/30 border-zinc-600/30 text-zinc-400 hover:border-zinc-500/50'
                  }`}
                >
                  <div className="text-base mb-0.5">{m.icon}</div>
                  <div className="text-xs font-medium">{m.label}</div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">{m.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Topic */}
          <div>
            <label className="text-xs text-zinc-400 block mb-1">Topic</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="What should agents discuss?"
              className="w-full bg-zinc-700/50 text-zinc-200 text-sm px-3 py-2 rounded-lg border border-zinc-600/50 focus:border-blue-500/50 focus:outline-none"
            />
          </div>

          {/* Agent selector */}
          <div>
            <label className="text-xs text-zinc-400 block mb-1">
              Participants ({selectedAgents.length} selected, min 2, max 7)
            </label>
            <div className="flex flex-wrap gap-1.5">
              {agents.map((a) => (
                <button
                  key={a.id}
                  onClick={() => toggleAgent(a.id)}
                  disabled={!selectedAgents.includes(a.id) && selectedAgents.length >= 7}
                  className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                    selectedAgents.includes(a.id)
                      ? 'bg-blue-600/20 text-blue-400 ring-1 ring-blue-500/40'
                      : 'bg-zinc-700/50 text-zinc-400 hover:bg-zinc-700 disabled:opacity-30'
                  }`}
                >{a.name}</button>
              ))}
            </div>
          </div>

          {/* Max rounds */}
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
            >{submitting ? 'Starting...' : 'Start Session'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
