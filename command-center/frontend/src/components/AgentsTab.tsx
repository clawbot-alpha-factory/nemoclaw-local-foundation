'use client';

import { useEffect, useState, useCallback } from 'react';
import type { AgentProfile, OrgLevel, WorkloadEntry } from '@/lib/agents-api';
import { fetchAgentProfiles, fetchOrgHierarchy, fetchWorkload } from '@/lib/agents-api';

const STATUS_STYLES: Record<string, { bg: string; dot: string; label: string }> = {
  active: { bg: 'bg-green-50 border border-green-200', dot: 'bg-nc-green', label: 'Active' },
  recent: { bg: 'bg-yellow-50 border border-yellow-200', dot: 'bg-nc-yellow', label: 'Recent' },
  idle: { bg: 'bg-gray-50 border border-gray-200', dot: 'bg-gray-400', label: 'Idle' },
};

const AUTHORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'CEO', color: 'text-amber-700 bg-amber-50 border border-amber-200' },
  2: { label: 'C-Suite', color: 'text-nc-accent bg-indigo-50 border border-indigo-200' },
  3: { label: 'Lead', color: 'text-nc-text-dim bg-nc-surface-2 border border-nc-border' },
};

function formatResponseTime(seconds: number | null): string {
  if (seconds === null) return '\u2014';
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)}m`;
}

function AgentDetail({ agent, onClose }: { agent: AgentProfile; onClose: () => void }) {
  const activity = agent.activity;
  const statusInfo = STATUS_STYLES[activity?.status || 'idle'];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-nc-bg border border-nc-border rounded-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-nc-bg border-b border-nc-border px-6 py-4 flex items-center justify-between rounded-t-xl">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{agent.avatar}</span>
            <div>
              <h2 className="text-lg font-semibold text-nc-text">{agent.name}</h2>
              <p className="text-sm text-nc-text-dim">{agent.title}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-nc-text-dim hover:text-nc-text transition-colors text-2xl leading-none px-2">&times;</button>
        </div>
        <div className="px-6 py-5 space-y-6">
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${AUTHORITY_LABELS[agent.authority_level]?.color || ''}`}>
              {AUTHORITY_LABELS[agent.authority_level]?.label || `L${agent.authority_level}`}
            </span>
            <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${statusInfo.bg}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${statusInfo.dot}`} />
              <span className="text-nc-text">{statusInfo.label}</span>
            </span>
            {activity?.avg_response_seconds != null && (
              <span className="text-xs text-nc-text-dim">Avg response: {formatResponseTime(activity.avg_response_seconds)}</span>
            )}
          </div>
          <div>
            <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-1.5">Role</h4>
            <p className="text-sm text-nc-text leading-relaxed">{agent.role}</p>
          </div>
          {agent.decides.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Key Decisions</h4>
              <div className="space-y-1.5">
                {agent.decides.map((d, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-nc-text">
                    <span className="text-nc-accent mt-0.5 flex-shrink-0">&bull;</span><span>{d}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {agent.capabilities.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Capabilities ({agent.capabilities.length})</h4>
              <div className="flex flex-wrap gap-1.5">
                {agent.capabilities.map((cap) => (
                  <span key={cap} className="text-xs text-nc-text bg-nc-surface-2 px-2.5 py-1 rounded border border-nc-border">{cap.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Active Skills ({agent.skills.primary_count})</h4>
              <div className="space-y-1">
                {agent.skills.primary.map((s) => (
                  <div key={s} className="text-xs text-green-700 bg-green-50 border border-green-200 px-2.5 py-1.5 rounded">{s}</div>
                ))}
                {agent.skills.primary.length === 0 && <p className="text-xs text-nc-text-dim italic">None assigned</p>}
              </div>
            </div>
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Planned Skills ({agent.skills.future_count})</h4>
              <div className="space-y-1">
                {agent.skills.future.map((s) => (
                  <div key={s} className="text-xs text-nc-text-dim bg-nc-surface px-2.5 py-1.5 rounded border border-nc-border">{s}</div>
                ))}
                {agent.skills.future.length === 0 && <p className="text-xs text-nc-text-dim italic">None planned</p>}
              </div>
            </div>
          </div>
          {activity && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Activity</h4>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { value: activity.total_messages, label: 'Total Msgs' },
                  { value: activity.messages_24h, label: 'Last 24h' },
                  { value: formatResponseTime(activity.avg_response_seconds), label: 'Avg Response' },
                  { value: activity.broadcast_messages, label: 'Broadcasts' },
                ].map((m) => (
                  <div key={m.label} className="bg-nc-surface border border-nc-border rounded-lg p-3 text-center">
                    <div className="text-lg font-semibold text-nc-text">{m.value}</div>
                    <div className="text-[10px] text-nc-text-dim uppercase mt-0.5">{m.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {agent.failure_modes.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Failure Modes</h4>
              <div className="space-y-1.5">
                {agent.failure_modes.map((fm, i) => (
                  <div key={i} className="text-xs text-nc-text bg-nc-surface border border-nc-border px-3 py-2 rounded">{fm}</div>
                ))}
              </div>
            </div>
          )}
          {agent.constraints.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">Constraints</h4>
              <div className="space-y-1.5">
                {agent.constraints.map((c, i) => (
                  <div key={i} className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded">{c}</div>
                ))}
              </div>
            </div>
          )}
          {agent.metrics_tracked.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-2">KPIs</h4>
              <div className="flex flex-wrap gap-1.5">
                {agent.metrics_tracked.map((m) => (
                  <span key={m} className="text-xs text-purple-700 bg-purple-50 border border-purple-200 px-2.5 py-1 rounded">{m.replace(/_/g, ' ')}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AgentCard({ agent, onClick }: { agent: AgentProfile; onClick: () => void }) {
  const activity = agent.activity;
  const statusInfo = STATUS_STYLES[activity?.status || 'idle'];
  return (
    <button onClick={onClick} className="w-full text-left bg-nc-bg hover:bg-nc-surface border border-nc-border hover:border-nc-accent/30 rounded-xl p-5 transition-all group shadow-sm hover:shadow-md">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{agent.avatar}</span>
          <div>
            <div className="font-semibold text-sm text-nc-text">{agent.name}</div>
            <div className="text-xs text-nc-text-dim">{agent.title}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusInfo.dot}`} />
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${AUTHORITY_LABELS[agent.authority_level]?.color || ''}`}>L{agent.authority_level}</span>
        </div>
      </div>
      <p className="text-xs text-nc-text-dim leading-relaxed line-clamp-2 mb-4">{agent.role}</p>
      <div className="flex items-center justify-between text-[11px] pt-3 border-t border-nc-border">
        <span className="text-nc-text font-medium">{agent.skills.primary_count} skills</span>
        <span className="text-nc-text-dim">{agent.capabilities.length} capabilities</span>
        {activity && <span className="text-nc-text-dim">{activity.total_messages} msgs</span>}
      </div>
    </button>
  );
}

function OrgChart({ hierarchy, onAgentClick }: { hierarchy: OrgLevel[]; onAgentClick: (id: string) => void }) {
  return (
    <div className="space-y-6">
      {hierarchy.map((level) => (
        <div key={level.level}>
          <div className="text-[11px] font-semibold text-nc-text-dim uppercase tracking-wider mb-3">{level.label} &mdash; Level {level.level}</div>
          <div className="flex flex-wrap gap-3">
            {level.agents.map((a) => (
              <button key={a.id} onClick={() => onAgentClick(a.id)} className="flex items-center gap-3 bg-nc-bg hover:bg-nc-surface border border-nc-border hover:border-nc-accent/30 rounded-lg px-4 py-3 transition-colors shadow-sm">
                <span className="text-xl">{a.avatar}</span>
                <div className="text-left">
                  <div className="text-sm font-medium text-nc-text">{a.name}</div>
                  <div className="text-[11px] text-nc-text-dim">{a.title}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function WorkloadTable({ team, onAgentClick }: { team: WorkloadEntry[]; onAgentClick: (id: string) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] text-nc-text-dim uppercase tracking-wider border-b border-nc-border bg-nc-surface">
            <th className="text-left py-3 px-4 font-semibold">Agent</th>
            <th className="text-center py-3 px-3 font-semibold">Status</th>
            <th className="text-center py-3 px-3 font-semibold">24h Msgs</th>
            <th className="text-center py-3 px-3 font-semibold">Total Msgs</th>
            <th className="text-center py-3 px-3 font-semibold">Avg Response</th>
            <th className="text-center py-3 px-3 font-semibold">Skills</th>
            <th className="text-center py-3 px-3 font-semibold">Capabilities</th>
          </tr>
        </thead>
        <tbody>
          {team.map((entry) => {
            const statusInfo = STATUS_STYLES[entry.status] || STATUS_STYLES.idle;
            return (
              <tr key={entry.id} onClick={() => onAgentClick(entry.id)} className="border-b border-nc-border hover:bg-nc-surface cursor-pointer transition-colors">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{entry.avatar}</span>
                    <div>
                      <div className="text-sm font-medium text-nc-text">{entry.name}</div>
                      <div className="text-[11px] text-nc-text-dim">{entry.title}</div>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-3 text-center">
                  <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${statusInfo.bg}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${statusInfo.dot}`} />
                    <span className="text-nc-text">{statusInfo.label}</span>
                  </span>
                </td>
                <td className="py-3 px-3 text-center text-nc-text font-medium">{entry.messages_24h}</td>
                <td className="py-3 px-3 text-center text-nc-text-dim">{entry.total_messages}</td>
                <td className="py-3 px-3 text-center text-nc-text-dim">{formatResponseTime(entry.avg_response_seconds)}</td>
                <td className="py-3 px-3 text-center text-nc-text">{entry.skills_assigned}</td>
                <td className="py-3 px-3 text-center text-nc-text-dim">{entry.capabilities_count}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type ViewMode = 'cards' | 'workload' | 'org';

export default function AgentsTab() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [hierarchy, setHierarchy] = useState<OrgLevel[]>([]);
  const [workload, setWorkload] = useState<WorkloadEntry[]>([]);
  const [summary, setSummary] = useState<{ total_agents: number; active_now: number; total_messages: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<AgentProfile | null>(null);
  const [view, setView] = useState<ViewMode>('cards');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [agentsData, orgData, workloadData] = await Promise.all([
        fetchAgentProfiles(), fetchOrgHierarchy(), fetchWorkload(),
      ]);
      setAgents(agentsData.agents);
      setHierarchy(orgData.hierarchy);
      setWorkload(workloadData.team);
      setSummary(workloadData.summary);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agent data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAgentClick = useCallback((agentId: string) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) setSelectedAgent(agent);
  }, [agents]);

  if (loading) return <div className="flex items-center justify-center h-full text-nc-text-dim text-sm">Loading agents...</div>;
  if (error) return <div className="flex items-center justify-center h-full text-nc-red text-sm">{error}</div>;

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-nc-text">Agent Team</h1>
            <p className="text-sm text-nc-text-dim mt-1">
              {summary?.total_agents} agents &middot; {summary?.active_now} active &middot; {summary?.total_messages} total messages
            </p>
          </div>
          <div className="flex items-center gap-1 bg-nc-surface-2 border border-nc-border rounded-lg p-1">
            {(['cards', 'workload', 'org'] as ViewMode[]).map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={`text-xs px-4 py-2 rounded-md transition-colors font-medium ${view === v ? 'bg-nc-bg text-nc-text shadow-sm border border-nc-border' : 'text-nc-text-dim hover:text-nc-text'}`}>
                {v === 'cards' ? 'Profiles' : v === 'workload' ? 'Workload' : 'Org Chart'}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { value: summary?.total_agents, label: 'Total Agents', color: 'text-nc-text' },
            { value: summary?.active_now, label: 'Active Now', color: 'text-nc-green' },
            { value: agents.reduce((sum, a) => sum + a.skills.primary_count, 0), label: 'Assigned Skills', color: 'text-nc-accent' },
            { value: agents.reduce((sum, a) => sum + a.capabilities.length, 0), label: 'Total Capabilities', color: 'text-purple-600' },
          ].map((card) => (
            <div key={card.label} className="bg-nc-bg border border-nc-border rounded-xl p-4 shadow-sm">
              <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
              <div className="text-xs text-nc-text-dim mt-1 font-medium">{card.label}</div>
            </div>
          ))}
        </div>

        {view === 'cards' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} onClick={() => setSelectedAgent(agent)} />
            ))}
          </div>
        )}
        {view === 'workload' && (
          <div className="bg-nc-bg border border-nc-border rounded-xl overflow-hidden shadow-sm">
            <WorkloadTable team={workload} onAgentClick={handleAgentClick} />
          </div>
        )}
        {view === 'org' && (
          <div className="bg-nc-bg border border-nc-border rounded-xl p-5 shadow-sm">
            <OrgChart hierarchy={hierarchy} onAgentClick={handleAgentClick} />
          </div>
        )}
      </div>
      {selectedAgent && <AgentDetail agent={selectedAgent} onClose={() => setSelectedAgent(null)} />}
    </div>
  );
}
