'use client';
import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Skill, SkillStats, GraphData, DryRunResult,
  fetchSkills, fetchSkillStats, fetchSkillGraph, dryRunSkill, reloadSkills
} from '../lib/skills-api';

// ── Badge helpers ──────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  built: 'bg-green-100 text-green-800',
  registered: 'bg-yellow-100 text-yellow-800',
};
const HEALTH_COLORS: Record<string, string> = {
  healthy: 'bg-green-100 text-green-800',
  missing_dependencies: 'bg-red-100 text-red-800',
  misconfigured: 'bg-red-100 text-red-800',
  unused: 'bg-gray-100 text-gray-600',
  not_built: 'bg-yellow-100 text-yellow-800',
};
const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-blue-100 text-blue-800',
  low: 'bg-gray-100 text-gray-600',
};
const TYPE_ICONS: Record<string, string> = {
  executor: '\u2699\uFE0F',
  analyzer: '\uD83D\uDD0D',
  generator: '\u2728',
  transformer: '\uD83D\uDD04',
};

function Badge({ text, colors }: { text: string; colors: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colors}`}>
      {text}
    </span>
  );
}

// ── Summary Cards ──────────────────────────────────────────────────────
function SummaryCards({ stats }: { stats: SkillStats | null }) {
  if (!stats) return null;
  const cards = [
    { label: 'Total Skills', value: stats.total, sub: `${stats.by_status.built || 0} built, ${stats.by_status.registered || 0} registered` },
    { label: 'Graph Edges', value: stats.graph.total_edges, sub: `${stats.graph.circular_deps} circular, ${stats.graph.orphans} orphans` },
    { label: 'Critical', value: stats.by_priority.critical || 0, sub: `${stats.by_priority.high || 0} high priority` },
    { label: 'Health Issues', value: (stats.by_health.missing_dependencies || 0) + (stats.by_health.misconfigured || 0), sub: `${stats.by_health.unused || 0} unused` },
  ];
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
      {cards.map(c => (
        <div key={c.label} className="bg-nc-surface-2 border border-nc-border rounded-lg p-3">
          <div className="text-2xl font-bold text-nc-text">{c.value}</div>
          <div className="text-sm font-medium text-nc-text">{c.label}</div>
          <div className="text-xs text-nc-text-dim mt-0.5">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Catalog View ───────────────────────────────────────────────────────
function CatalogView({ skills, onSelect }: { skills: Skill[]; onSelect: (s: Skill) => void }) {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterHealth, setFilterHealth] = useState('');

  const filtered = useMemo(() => {
    return skills.filter(s => {
      if (search) {
        const q = search.toLowerCase();
        const hay = `${s.id} ${s.display_name} ${s.description} ${s.tag}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filterStatus && s.status !== filterStatus) return false;
      if (filterPriority && s.priority !== filterPriority) return false;
      if (filterHealth && s.health !== filterHealth) return false;
      return true;
    });
  }, [skills, search, filterStatus, filterPriority, filterHealth]);

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        <input
          type="text"
          placeholder="Search skills..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] px-3 py-1.5 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
        />
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="px-2 py-1.5 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text">
          <option value="">All Status</option>
          <option value="built">Built</option>
          <option value="registered">Registered</option>
        </select>
        <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)}
          className="px-2 py-1.5 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text">
          <option value="">All Priority</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={filterHealth} onChange={e => setFilterHealth(e.target.value)}
          className="px-2 py-1.5 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text">
          <option value="">All Health</option>
          <option value="healthy">Healthy</option>
          <option value="missing_dependencies">Missing Deps</option>
          <option value="unused">Unused</option>
          <option value="not_built">Not Built</option>
        </select>
      </div>
      <div className="text-xs text-nc-text-dim mb-2">{filtered.length} of {skills.length} skills</div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {filtered.map(skill => (
          <div
            key={skill.id}
            onClick={() => onSelect(skill)}
            className="bg-nc-surface border border-nc-border rounded-lg p-3 cursor-pointer hover:border-nc-accent transition-colors"
          >
            <div className="flex items-start justify-between mb-1">
              <div className="font-medium text-sm text-nc-text truncate flex-1 mr-2">
                {TYPE_ICONS[skill.skill_type] || ''} {skill.display_name}
              </div>
              <Badge text={skill.status} colors={STATUS_COLORS[skill.status] || ''} />
            </div>
            <div className="text-xs text-nc-text-dim line-clamp-2 mb-2">{skill.description}</div>
            <div className="flex flex-wrap gap-1">
              <Badge text={skill.priority} colors={PRIORITY_COLORS[skill.priority] || ''} />
              <Badge text={skill.health} colors={HEALTH_COLORS[skill.health] || ''} />
              {skill.domain && <Badge text={`D:${skill.domain}`} colors="bg-nc-surface-2 text-nc-text-dim" />}
              {skill.assigned_agent && (
                <Badge text={skill.assigned_agent.replace(/_/g, ' ')} colors="bg-blue-50 text-blue-700" />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Graph View ─────────────────────────────────────────────────────────
function GraphView({ graph }: { graph: GraphData | null }) {
  if (!graph) return <div className="text-nc-text-dim text-sm">Loading graph...</div>;

  const { risks, stats } = graph;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          { label: 'Nodes', value: stats.total_nodes },
          { label: 'Edges', value: stats.total_edges },
          { label: 'Circular', value: stats.circular_count, warn: stats.circular_count > 0 },
          { label: 'Orphans', value: stats.orphan_count, warn: stats.orphan_count > 0 },
          { label: 'Overloaded', value: stats.overloaded_count, warn: stats.overloaded_count > 0 },
        ].map(c => (
          <div key={c.label} className={`border rounded-lg p-3 ${c.warn ? 'border-red-300 bg-red-50' : 'border-nc-border bg-nc-surface-2'}`}>
            <div className={`text-xl font-bold ${c.warn ? 'text-red-700' : 'text-nc-text'}`}>{c.value}</div>
            <div className="text-xs text-nc-text-dim">{c.label}</div>
          </div>
        ))}
      </div>

      {risks.circular.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <div className="font-medium text-sm text-red-800 mb-1">Circular Dependencies Detected</div>
          {risks.circular.map((cycle, i) => (
            <div key={i} className="text-xs text-red-700 font-mono">{cycle.join(' \u2192 ')}</div>
          ))}
        </div>
      )}

      {risks.orphans.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <div className="font-medium text-sm text-yellow-800 mb-1">Orphan Skills (no connections)</div>
          <div className="flex flex-wrap gap-1">
            {risks.orphans.map(id => (
              <Badge key={id} text={id} colors="bg-yellow-100 text-yellow-800" />
            ))}
          </div>
        </div>
      )}

      {risks.overloaded.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
          <div className="font-medium text-sm text-orange-800 mb-1">Overloaded Skills (5+ dependents)</div>
          <div className="flex flex-wrap gap-1">
            {risks.overloaded.map(id => (
              <Badge key={id} text={id} colors="bg-orange-100 text-orange-800" />
            ))}
          </div>
        </div>
      )}

      <div className="bg-nc-surface border border-nc-border rounded-lg p-3">
        <div className="font-medium text-sm text-nc-text mb-2">Edge List ({graph.edges.length})</div>
        <div className="max-h-64 overflow-y-auto space-y-0.5">
          {graph.edges.map((e, i) => (
            <div key={i} className="text-xs font-mono text-nc-text-dim">
              {e.source} <span className="text-nc-accent">\u2192</span> {e.target}
              <span className="text-nc-text-dim ml-1">({e.type})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Agent Mapping View ─────────────────────────────────────────────────
function AgentMappingView({ skills }: { skills: Skill[] }) {
  const agentMap = useMemo(() => {
    const map: Record<string, { primary: Skill[]; future: Skill[] }> = {};
    skills.forEach(s => {
      const agent = s.assigned_agent || 'unassigned';
      if (!map[agent]) map[agent] = { primary: [], future: [] };
      if (s.status === 'built') map[agent].primary.push(s);
      else map[agent].future.push(s);
    });
    return Object.entries(map).sort((a, b) =>
      (b[1].primary.length + b[1].future.length) - (a[1].primary.length + a[1].future.length)
    );
  }, [skills]);

  return (
    <div className="space-y-3">
      {agentMap.map(([agent, data]) => (
        <div key={agent} className="bg-nc-surface border border-nc-border rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium text-sm text-nc-text">{agent.replace(/_/g, ' ')}</div>
            <div className="text-xs text-nc-text-dim">{data.primary.length + data.future.length} skills</div>
          </div>
          {data.primary.length > 0 && (
            <div className="mb-2">
              <div className="text-xs font-medium text-green-700 mb-1">Primary ({data.primary.length})</div>
              <div className="flex flex-wrap gap-1">
                {data.primary.map(s => (
                  <span key={s.id} className="inline-block px-2 py-0.5 rounded text-xs bg-green-50 text-green-800 border border-green-200">
                    {s.display_name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.future.length > 0 && (
            <div>
              <div className="text-xs font-medium text-yellow-700 mb-1">Registered ({data.future.length})</div>
              <div className="flex flex-wrap gap-1">
                {data.future.map(s => (
                  <span key={s.id} className="inline-block px-2 py-0.5 rounded text-xs bg-yellow-50 text-yellow-800 border border-yellow-200">
                    {s.display_name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Skill Detail Modal ─────────────────────────────────────────────────
function SkillDetailModal({ skill, onClose, onDryRun }: {
  skill: Skill;
  onClose: () => void;
  onDryRun: (id: string) => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-12 px-4" onClick={onClose}>
      <div className="bg-nc-surface border border-nc-border rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-5"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-lg font-bold text-nc-text">{skill.display_name}</h2>
            <div className="text-xs text-nc-text-dim font-mono">{skill.id} v{skill.version}</div>
          </div>
          <button onClick={onClose} className="text-nc-text-dim hover:text-nc-text text-xl leading-none">&times;</button>
        </div>

        <div className="flex flex-wrap gap-1 mb-3">
          <Badge text={skill.status} colors={STATUS_COLORS[skill.status] || ''} />
          <Badge text={skill.priority} colors={PRIORITY_COLORS[skill.priority] || ''} />
          <Badge text={skill.health} colors={HEALTH_COLORS[skill.health] || ''} />
          {skill.skill_type && <Badge text={skill.skill_type} colors="bg-nc-surface-2 text-nc-text-dim" />}
          {skill.routing && <Badge text={`route: ${skill.routing}`} colors="bg-nc-surface-2 text-nc-text-dim" />}
        </div>

        {skill.health_reason && (
          <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded mb-2">{skill.health_reason}</div>
        )}

        <p className="text-sm text-nc-text mb-3">{skill.description}</p>

        {skill.assigned_agent && (
          <div className="text-xs text-nc-text-dim mb-3">
            <span className="font-medium">Agent:</span> {skill.assigned_agent.replace(/_/g, ' ')}
          </div>
        )}

        {skill.inputs.length > 0 && (
          <div className="mb-3">
            <div className="text-xs font-medium text-nc-text mb-1">Inputs ({skill.inputs.length})</div>
            <div className="space-y-1">
              {skill.inputs.map((inp, i) => (
                <div key={i} className="text-xs bg-nc-surface-2 rounded px-2 py-1">
                  <span className="font-mono font-medium text-nc-text">
                    {typeof inp === 'string' ? inp : inp.name}
                  </span>
                  {typeof inp === 'object' && inp.required && <span className="text-red-500 ml-1">*</span>}
                  {typeof inp === 'object' && inp.type && <span className="text-nc-text-dim ml-1">({inp.type})</span>}
                  {typeof inp === 'object' && inp.description && (
                    <span className="text-nc-text-dim ml-1">\u2014 {inp.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {skill.steps.length > 0 && (
          <div className="mb-3">
            <div className="text-xs font-medium text-nc-text mb-1">Execution Steps ({skill.steps.length})</div>
            <div className="space-y-1">
              {skill.steps.map((step, i) => (
                <div key={i} className="text-xs flex items-center gap-2 bg-nc-surface-2 rounded px-2 py-1">
                  <span className="font-mono text-nc-accent">{step.id}</span>
                  <span className="text-nc-text">{step.name}</span>
                  <Badge text={step.step_type} colors="bg-nc-surface text-nc-text-dim" />
                </div>
              ))}
            </div>
          </div>
        )}

        {(skill.composable.feeds_into.length > 0 || skill.composable.accepts_from.length > 0) && (
          <div className="mb-3">
            <div className="text-xs font-medium text-nc-text mb-1">Connections</div>
            {skill.composable.accepts_from.length > 0 && (
              <div className="text-xs text-nc-text-dim mb-1">
                <span className="font-medium">Accepts from:</span> {skill.composable.accepts_from.join(', ')}
              </div>
            )}
            {skill.composable.feeds_into.length > 0 && (
              <div className="text-xs text-nc-text-dim">
                <span className="font-medium">Feeds into:</span> {skill.composable.feeds_into.join(', ')}
              </div>
            )}
          </div>
        )}

        {skill.contracts && (skill.contracts.max_cost_usd || skill.contracts.max_execution_seconds) && (
          <div className="mb-3">
            <div className="text-xs font-medium text-nc-text mb-1">Contracts</div>
            <div className="text-xs text-nc-text-dim">
              {skill.contracts.max_cost_usd && <span className="mr-3">Max cost: ${skill.contracts.max_cost_usd}</span>}
              {skill.contracts.max_execution_seconds && <span className="mr-3">Max time: {skill.contracts.max_execution_seconds}s</span>}
              {skill.contracts.min_quality_score && <span>Min quality: {skill.contracts.min_quality_score}</span>}
            </div>
          </div>
        )}

        {skill.declarative_guarantees.length > 0 && (
          <div className="mb-3">
            <div className="text-xs font-medium text-nc-text mb-1">Guarantees</div>
            <ul className="text-xs text-nc-text-dim space-y-0.5">
              {skill.declarative_guarantees.map((g, i) => (
                <li key={i}>\u2022 {g}</li>
              ))}
            </ul>
          </div>
        )}

        {skill.status === 'built' && (
          <button
            onClick={() => onDryRun(skill.id)}
            className="w-full mt-2 px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Run Dry-Run Validation
          </button>
        )}
      </div>
    </div>
  );
}

// ── Dry Run Panel ──────────────────────────────────────────────────────
function DryRunPanel({ skills, initialSkillId, onClose }: {
  skills: Skill[];
  initialSkillId?: string;
  onClose: () => void;
}) {
  const builtSkills = useMemo(() => skills.filter(s => s.status === 'built'), [skills]);
  const [selectedId, setSelectedId] = useState(initialSkillId || (builtSkills[0]?.id ?? ''));
  const [inputValues, setInputValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<DryRunResult | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedSkill = useMemo(() => skills.find(s => s.id === selectedId), [skills, selectedId]);

  useEffect(() => {
    setInputValues({});
    setResult(null);
  }, [selectedId]);

  const handleRun = async () => {
    if (!selectedId) return;
    setLoading(true);
    try {
      const r = await dryRunSkill(selectedId, inputValues);
      setResult(r);
    } catch (e) {
      setResult({ skill_id: selectedId, display_name: '', passed: false, errors: [String(e)], input_schema: [], provided_inputs: {}, dependency_chain: { upstream: [], downstream: [] } } as DryRunResult);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-sm text-nc-text">Dry-Run Execution Console</h3>
        <button onClick={onClose} className="text-xs text-nc-text-dim hover:text-nc-text">Back to Catalog</button>
      </div>

      <select value={selectedId} onChange={e => setSelectedId(e.target.value)}
        className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text">
        {builtSkills.map(s => (
          <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
        ))}
      </select>

      {selectedSkill && selectedSkill.inputs.length > 0 && (
        <div className="bg-nc-surface-2 border border-nc-border rounded-lg p-3">
          <div className="text-xs font-medium text-nc-text mb-2">Inputs</div>
          <div className="space-y-2">
            {selectedSkill.inputs.filter(inp => typeof inp === 'object').map((inp, i) => (
              <div key={i}>
                <label className="text-xs text-nc-text">
                  {inp.name} {inp.required && <span className="text-red-500">*</span>}
                  {inp.type && <span className="text-nc-text-dim ml-1">({inp.type})</span>}
                </label>
                <textarea
                  rows={2}
                  placeholder={inp.description || ''}
                  value={inputValues[inp.name] || ''}
                  onChange={e => setInputValues(prev => ({ ...prev, [inp.name]: e.target.value }))}
                  className="w-full mt-0.5 px-2 py-1 text-xs border border-nc-border rounded bg-nc-surface text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent resize-y"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={handleRun}
        disabled={loading || !selectedId}
        className="w-full px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {loading ? 'Validating...' : 'Run Dry Validation'}
      </button>

      {result && (
        <div className={`border rounded-lg p-3 ${result.passed ? 'border-green-300 bg-green-50' : 'border-red-300 bg-red-50'}`}>
          <div className={`font-medium text-sm mb-2 ${result.passed ? 'text-green-800' : 'text-red-800'}`}>
            {result.passed ? '\u2705 Validation Passed' : '\u274C Validation Failed'}
          </div>

          {result.errors && result.errors.length > 0 && (
            <div className="mb-2">
              <div className="text-xs font-medium text-red-700">Errors:</div>
              {result.errors.map((e, i) => (
                <div key={i} className="text-xs text-red-600">\u2022 {e}</div>
              ))}
            </div>
          )}

          {result.warnings && result.warnings.length > 0 && (
            <div className="mb-2">
              <div className="text-xs font-medium text-yellow-700">Warnings:</div>
              {result.warnings.map((w, i) => (
                <div key={i} className="text-xs text-yellow-600">\u2022 {w}</div>
              ))}
            </div>
          )}

          {result.estimated_cost && (
            <div className="text-xs text-nc-text-dim">
              <span className="mr-3">Cost: {result.estimated_cost}</span>
              <span className="mr-3">Time: {result.estimated_time}</span>
              <span>Routing: {result.routing}</span>
            </div>
          )}

          {result.dependency_chain && (
            <div className="mt-2">
              <div className="text-xs font-medium text-nc-text">Dependency Chain</div>
              {result.dependency_chain.upstream.length > 0 && (
                <div className="text-xs text-nc-text-dim">
                  Upstream: {result.dependency_chain.upstream.map(d => d.display_name).join(', ')}
                </div>
              )}
              {result.dependency_chain.downstream.length > 0 && (
                <div className="text-xs text-nc-text-dim">
                  Downstream: {result.dependency_chain.downstream.map(d => d.display_name).join(', ')}
                </div>
              )}
            </div>
          )}

          {result.steps && result.steps.length > 0 && (
            <div className="mt-2">
              <div className="text-xs font-medium text-nc-text">Execution Steps</div>
              {result.steps.map((step, i) => (
                <div key={i} className="text-xs text-nc-text-dim font-mono">
                  {step.id}: {step.name} [{step.step_type}]
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Tab ───────────────────────────────────────────────────────────
type View = 'catalog' | 'graph' | 'agents' | 'dryrun';

export default function SkillsTab() {
  const [view, setView] = useState<View>('catalog');
  const [skills, setSkills] = useState<Skill[]>([]);
  const [stats, setStats] = useState<SkillStats | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [dryRunSkillId, setDryRunSkillId] = useState<string | undefined>();
  const [reloading, setReloading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [skillsRes, statsRes, graphRes] = await Promise.all([
        fetchSkills(),
        fetchSkillStats(),
        fetchSkillGraph(),
      ]);
      setSkills(skillsRes.skills);
      setStats(statsRes);
      setGraph(graphRes);
    } catch (e) {
      console.error('Failed to load skills:', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleReload = async () => {
    setReloading(true);
    try {
      await reloadSkills();
      await load();
    } finally {
      setReloading(false);
    }
  };

  const handleDryRunFromModal = (skillId: string) => {
    setSelectedSkill(null);
    setDryRunSkillId(skillId);
    setView('dryrun');
  };

  const views: { key: View; label: string }[] = [
    { key: 'catalog', label: 'Catalog' },
    { key: 'graph', label: 'Dependency Graph' },
    { key: 'agents', label: 'Agent Mapping' },
    { key: 'dryrun', label: 'Dry Run' },
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-nc-border">
        <div className="flex gap-1">
          {views.map(v => (
            <button
              key={v.key}
              onClick={() => setView(v.key)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                view === v.key
                  ? 'bg-nc-accent text-white'
                  : 'text-nc-text-dim hover:bg-nc-surface-2'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <button
          onClick={handleReload}
          disabled={reloading}
          className="px-3 py-1.5 text-xs border border-nc-border rounded-lg text-nc-text-dim hover:bg-nc-surface-2 disabled:opacity-50"
        >
          {reloading ? 'Reloading...' : 'Reload'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <SummaryCards stats={stats} />

        {view === 'catalog' && <CatalogView skills={skills} onSelect={setSelectedSkill} />}
        {view === 'graph' && <GraphView graph={graph} />}
        {view === 'agents' && <AgentMappingView skills={skills} />}
        {view === 'dryrun' && (
          <DryRunPanel
            skills={skills}
            initialSkillId={dryRunSkillId}
            onClose={() => setView('catalog')}
          />
        )}
      </div>

      {selectedSkill && (
        <SkillDetailModal
          skill={selectedSkill}
          onClose={() => setSelectedSkill(null)}
          onDryRun={handleDryRunFromModal}
        />
      )}
    </div>
  );
}
