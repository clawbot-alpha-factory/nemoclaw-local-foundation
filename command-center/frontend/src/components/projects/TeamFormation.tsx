'use client';

import { useState, useEffect } from 'react';
import { fetchProjectTeam, assignAgentToProject } from '@/lib/projects-api';
import { fetchAgentProfiles } from '@/lib/agents-api';
import type { TeamMember } from '@/lib/projects-api';
import type { AgentProfile } from '@/lib/agents-api';

interface Props {
  projectId: string;
}

export default function TeamFormation({ projectId }: Props) {
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAssign, setShowAssign] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [role, setRole] = useState('');
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    Promise.all([
      fetchProjectTeam(projectId).catch(() => ({ members: [], total: 0 })),
      fetchAgentProfiles().catch(() => ({ agents: [], total: 0 })),
    ]).then(([teamData, agentData]) => {
      setTeam(teamData.members);
      setAgents(agentData.agents);
    }).finally(() => setLoading(false));
  }, [projectId]);

  async function handleAssign() {
    if (!selectedAgent || !role.trim()) return;
    setAssigning(true);
    try {
      const member = await assignAgentToProject(projectId, selectedAgent, role.trim());
      setTeam(prev => [...prev, member]);
      setShowAssign(false);
      setSelectedAgent('');
      setRole('');
    } catch (err) {
      console.error('Assign error:', err);
    } finally {
      setAssigning(false);
    }
  }

  if (loading) return <div className="text-sm text-nc-text-dim animate-pulse p-4">Loading team...</div>;

  const assignedIds = new Set(team.map(m => m.agent_id));
  const availableAgents = agents.filter(a => !assignedIds.has(a.id));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-nc-text">Team ({team.length})</h4>
        <button
          onClick={() => setShowAssign(!showAssign)}
          className="px-2.5 py-1 text-xs bg-nc-accent/20 text-nc-accent rounded-lg hover:bg-nc-accent/30 transition-colors"
        >+ Assign Agent</button>
      </div>

      {/* Assign form */}
      {showAssign && (
        <div className="bg-nc-surface-2 rounded-lg p-3 border border-nc-border space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="bg-nc-surface text-nc-text text-sm px-2 py-1.5 rounded-lg border border-nc-border"
            >
              <option value="">Select agent...</option>
              {availableAgents.map(a => (
                <option key={a.id} value={a.id}>{a.name} — {a.title}</option>
              ))}
            </select>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Role (e.g. Lead, Reviewer)"
              className="bg-nc-surface text-nc-text text-sm px-2 py-1.5 rounded-lg border border-nc-border"
            />
          </div>
          <button
            onClick={handleAssign}
            disabled={assigning || !selectedAgent || !role.trim()}
            className="px-3 py-1.5 text-xs bg-nc-accent text-white rounded-lg disabled:opacity-50"
          >{assigning ? 'Assigning...' : 'Assign'}</button>
        </div>
      )}

      {/* Team list */}
      <div className="space-y-2">
        {team.map((m) => (
          <div key={m.agent_id} className="bg-nc-surface rounded-lg border border-nc-border p-3 flex items-center gap-3">
            <span className="text-lg">🤖</span>
            <div className="flex-1">
              <div className="text-sm font-medium text-nc-text">{m.agent_name}</div>
              <div className="text-xs text-nc-text-dim">{m.role}</div>
            </div>
            <div className="text-[10px] text-nc-text-dim">
              {new Date(m.assigned_at).toLocaleDateString()}
            </div>
          </div>
        ))}
        {team.length === 0 && (
          <div className="text-center py-6 text-sm text-nc-text-dim">No agents assigned yet</div>
        )}
      </div>
    </div>
  );
}
