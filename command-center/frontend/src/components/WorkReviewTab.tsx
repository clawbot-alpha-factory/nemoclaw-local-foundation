'use client';

import { useEffect, useState, useCallback } from 'react';
import { fetchAgentProfiles } from '@/lib/agents-api';
import type { AgentProfile } from '@/lib/agents-api';
import { API_BASE } from '@/lib/config';

// ── Types ──────────────────────────────────────────────────────────

interface WorkItem {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_avatar: string;
  task: string;
  description: string;
  status: 'completed' | 'failed' | 'running';
  quality_score: number | null;
  timestamp: string;
  outputs?: string[];
  raw_output?: string;
}

type Period = 'today' | 'week' | 'all';

// ── Helpers ────────────────────────────────────────────────────────

import { headers } from '@/lib/auth';

async function fetchWorkLog(agentId: string, period: Period): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/agents/${agentId}/work-log?period=${period}`, { headers: headers() });
  if (!res.ok) return {};
  return res.json();
}

async function fetchExecutionHistory(limit = 50): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/execution/history?limit=${limit}`, { headers: headers() });
  if (!res.ok) return {};
  return res.json();
}

function formatTime(ts: string): string {
  const d = new Date(ts);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function scoreColor(score: number | null): string {
  if (score === null) return 'text-nc-text-muted';
  if (score >= 9) return 'text-nc-green';
  if (score >= 7) return 'text-nc-yellow';
  return 'text-nc-red';
}

function scoreBg(score: number | null): string {
  if (score === null) return 'bg-nc-surface-2';
  if (score >= 9) return 'bg-nc-green/10';
  if (score >= 7) return 'bg-nc-yellow/10';
  return 'bg-nc-red/10';
}

function statusBadge(status: string): { label: string; cls: string } {
  switch (status) {
    case 'completed': return { label: 'Done', cls: 'bg-nc-green/15 text-nc-green' };
    case 'failed': return { label: 'Failed', cls: 'bg-nc-red/15 text-nc-red' };
    case 'running': return { label: 'Running', cls: 'bg-nc-accent/15 text-nc-accent' };
    default: return { label: status, cls: 'bg-nc-surface-2 text-nc-text-dim' };
  }
}

// ── Component ──────────────────────────────────────────────────────

export default function WorkReviewTab() {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('all');
  const [period, setPeriod] = useState<Period>('today');
  const [search, setSearch] = useState('');
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [loading, setLoading] = useState(true);

  // Load agents
  useEffect(() => {
    fetchAgentProfiles()
      .then((data) => setAgents(data.agents || []))
      .catch(() => {});
  }, []);

  // Load work items
  const loadWork = useCallback(async () => {
    setLoading(true);
    try {
      const items: WorkItem[] = [];
      const agentList = selectedAgent === 'all' ? agents : agents.filter(a => a.id === selectedAgent);

      // Fetch work logs per agent
      const logPromises = agentList.map(async (agent) => {
        try {
          const data = await fetchWorkLog(agent.id, period);
          const entries = (data as Record<string, unknown>).entries as Array<Record<string, unknown>> || [];
          for (const entry of entries) {
            items.push({
              id: `${agent.id}-${entry.timestamp || Date.now()}`,
              agent_id: agent.id,
              agent_name: agent.name || agent.character_name,
              agent_avatar: agent.avatar,
              task: (entry.task as string) || (entry.goal as string) || 'Untitled task',
              description: (entry.description as string) || (entry.summary as string) || '',
              status: (entry.status as 'completed' | 'failed' | 'running') || 'completed',
              quality_score: typeof entry.quality_score === 'number' ? entry.quality_score : null,
              timestamp: (entry.timestamp as string) || new Date().toISOString(),
              outputs: (entry.outputs as string[]) || [],
              raw_output: (entry.raw_output as string) || (entry.output as string) || '',
            });
          }
        } catch { /* skip agent on error */ }
      });

      await Promise.all(logPromises);

      // Also fetch execution history
      try {
        const history = await fetchExecutionHistory();
        const executions = (history as Record<string, unknown>).executions as Array<Record<string, unknown>> || [];
        for (const exec of executions) {
          const agentId = (exec.agent_id as string) || '';
          if (selectedAgent !== 'all' && agentId !== selectedAgent) continue;
          const existing = items.find(i => i.id === exec.execution_id);
          if (existing) continue;
          const agent = agents.find(a => a.id === agentId);
          items.push({
            id: (exec.execution_id as string) || `exec-${Date.now()}-${Math.random()}`,
            agent_id: agentId,
            agent_name: agent?.name || agent?.character_name || agentId,
            agent_avatar: agent?.avatar || '🤖',
            task: (exec.skill_id as string) || (exec.goal as string) || 'Execution',
            description: (exec.description as string) || '',
            status: (exec.status as 'completed' | 'failed' | 'running') || 'completed',
            quality_score: typeof exec.quality_score === 'number' ? exec.quality_score : null,
            timestamp: (exec.created_at as string) || (exec.timestamp as string) || new Date().toISOString(),
            outputs: (exec.outputs as string[]) || [],
            raw_output: (exec.output as string) || '',
          });
        }
      } catch { /* execution history optional */ }

      // Sort by time descending
      items.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setWorkItems(items);
    } catch (e) {
      console.error('Failed to load work items:', e);
    } finally {
      setLoading(false);
    }
  }, [agents, selectedAgent, period]);

  useEffect(() => {
    if (agents.length > 0) loadWork();
  }, [agents, loadWork]);

  // Filter by search
  const filtered = search.trim()
    ? workItems.filter(
        (w) =>
          w.task.toLowerCase().includes(search.toLowerCase()) ||
          w.agent_name.toLowerCase().includes(search.toLowerCase()) ||
          w.description.toLowerCase().includes(search.toLowerCase())
      )
    : workItems;

  function handleDownload(item: WorkItem) {
    const content = item.raw_output || item.description || 'No output available';
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.task.replace(/\s+/g, '-').toLowerCase()}-output.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function handleExportAll() {
    const lines = filtered.map((w) =>
      `## ${w.task}\n- Agent: ${w.agent_name}\n- Status: ${w.status}\n- Quality: ${w.quality_score ?? 'N/A'}/10\n- Time: ${w.timestamp}\n${w.description ? `\n${w.description}\n` : ''}`
    );
    const content = `# Work Review Report\nExported: ${new Date().toISOString()}\n\n${lines.join('\n---\n\n')}`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `work-review-${period}-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const periods: { value: Period; label: string }[] = [
    { value: 'today', label: 'Today' },
    { value: 'week', label: 'This Week' },
    { value: 'all', label: 'All Time' },
  ];

  return (
    <div className="flex flex-col h-full bg-nc-bg overflow-hidden">
      {/* Filters bar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-nc-border bg-nc-surface">
        {/* Agent dropdown */}
        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          className="bg-nc-surface-2 text-nc-text text-xs px-3 py-2 rounded-lg border border-nc-border focus:border-nc-accent focus:outline-none"
        >
          <option value="all">All Agents</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.avatar} {a.name || a.character_name}
            </option>
          ))}
        </select>

        {/* Period pills */}
        <div className="flex gap-1">
          {periods.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                period === p.value
                  ? 'bg-nc-accent text-white'
                  : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex-1">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search work items..."
            className="w-full max-w-xs bg-nc-surface-2 text-nc-text text-xs px-3 py-2 rounded-lg border border-nc-border focus:border-nc-accent focus:outline-none placeholder:text-nc-text-muted"
          />
        </div>

        {/* Export */}
        <button
          onClick={handleExportAll}
          disabled={filtered.length === 0}
          className="text-xs px-3 py-2 rounded-lg bg-nc-surface-2 text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2 transition-colors disabled:opacity-50"
        >
          Export MD
        </button>

        {/* Count */}
        <span className="text-xs text-nc-text-muted">{filtered.length} items</span>
      </div>

      {/* Main content: master-detail */}
      <div className="flex flex-1 min-h-0">
        {/* Work items list */}
        <div className="w-96 flex-shrink-0 border-r border-nc-border overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full text-nc-text-dim text-sm">
              Loading work items...
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-nc-text-dim text-sm">
              <span className="text-3xl mb-2">📝</span>
              <p>No work items found</p>
              <p className="text-xs text-nc-text-muted mt-1">
                Try changing the filters above
              </p>
            </div>
          ) : (
            <div className="py-1">
              {filtered.map((item) => {
                const badge = statusBadge(item.status);
                const isSelected = selectedItem?.id === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className={`w-full text-left px-4 py-3 border-b border-nc-border transition-colors ${
                      isSelected
                        ? 'bg-nc-accent/10'
                        : 'hover:bg-nc-surface-2'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-lg flex-shrink-0">{item.agent_avatar}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-nc-text truncate">{item.task}</span>
                          {item.quality_score !== null && item.quality_score >= 9 && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-nc-green/15 text-nc-green font-medium flex-shrink-0">
                              Publish
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-nc-text-dim">{item.agent_name}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badge.cls}`}>
                            {badge.label}
                          </span>
                          {item.quality_score !== null && (
                            <span className={`text-[10px] font-bold ${scoreColor(item.quality_score)}`}>
                              {item.quality_score}/10
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-nc-text-muted mt-0.5 block">
                          {formatTime(item.timestamp)}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          {selectedItem ? (
            <div className="p-6 space-y-5">
              {/* Header */}
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-nc-text">{selectedItem.task}</h2>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-sm text-nc-text-dim">
                      {selectedItem.agent_avatar} {selectedItem.agent_name}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusBadge(selectedItem.status).cls}`}>
                      {statusBadge(selectedItem.status).label}
                    </span>
                    <span className="text-xs text-nc-text-muted">
                      {formatTime(selectedItem.timestamp)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => handleDownload(selectedItem)}
                  className="text-xs px-3 py-2 rounded-lg bg-nc-accent hover:bg-nc-accent-dim text-white transition-colors"
                >
                  Download
                </button>
              </div>

              {/* Quality score card */}
              {selectedItem.quality_score !== null && (
                <div className={`p-4 rounded-xl ${scoreBg(selectedItem.quality_score)} border border-nc-border`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-nc-text-dim uppercase tracking-wider">Quality Score</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-2xl font-bold ${scoreColor(selectedItem.quality_score)}`}>
                        {selectedItem.quality_score}
                      </span>
                      <span className="text-sm text-nc-text-muted">/10</span>
                    </div>
                  </div>
                  {selectedItem.quality_score >= 9 && (
                    <div className="mt-2 text-xs text-nc-green font-medium">
                      Ready to Publish
                    </div>
                  )}
                </div>
              )}

              {/* Description */}
              {selectedItem.description && (
                <div>
                  <h3 className="text-xs font-medium text-nc-text-dim uppercase tracking-wider mb-2">Summary</h3>
                  <p className="text-sm text-nc-text leading-relaxed">{selectedItem.description}</p>
                </div>
              )}

              {/* Files */}
              {selectedItem.outputs && selectedItem.outputs.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-nc-text-dim uppercase tracking-wider mb-2">Files Produced</h3>
                  <div className="space-y-1">
                    {selectedItem.outputs.map((file, idx) => (
                      <div key={idx} className="flex items-center gap-2 px-3 py-2 bg-nc-surface-2 rounded-lg">
                        <span className="text-xs">📄</span>
                        <span className="text-xs text-nc-text truncate flex-1">{file}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw output */}
              {selectedItem.raw_output && (
                <div>
                  <h3 className="text-xs font-medium text-nc-text-dim uppercase tracking-wider mb-2">Raw Output</h3>
                  <pre className="text-xs text-nc-text-dim bg-nc-surface-2 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap font-mono border border-nc-border max-h-80 overflow-y-auto">
                    {selectedItem.raw_output}
                  </pre>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-nc-text-dim">
              <span className="text-4xl mb-3">📝</span>
              <p className="text-sm">Select a work item to view details</p>
              <p className="text-xs text-nc-text-muted mt-1">
                Download outputs, review quality scores, and export reports
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
