'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── Types ──────────────────────────────────────────────────────────────────

type TemplateId = 'social_intelligence' | 'competitor_analysis' | 'market_research' | 'trend_detection';

interface TemplateConfig {
  label: string;
  description: string;
  fields: { key: string; label: string; placeholder: string; type?: 'text' | 'textarea' }[];
}

interface ResearchRun {
  id: string;
  template: TemplateId;
  inputs: Record<string, string>;
  status: 'running' | 'completed' | 'failed';
  result: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
}

// ─── Template Definitions ───────────────────────────────────────────────────

const TEMPLATES: Record<TemplateId, TemplateConfig> = {
  social_intelligence: {
    label: 'Social Intelligence',
    description: 'Analyze social media presence, sentiment, and engagement patterns',
    fields: [
      { key: 'target', label: 'Target', placeholder: 'Brand, person, or topic' },
      { key: 'platforms', label: 'Platforms', placeholder: 'twitter, linkedin, reddit' },
      { key: 'timeframe', label: 'Timeframe', placeholder: 'last 7 days' },
    ],
  },
  competitor_analysis: {
    label: 'Competitor Analysis',
    description: 'Deep-dive into competitor positioning, features, and strategy',
    fields: [
      { key: 'company', label: 'Your Company', placeholder: 'Company name' },
      { key: 'competitors', label: 'Competitors', placeholder: 'Comma-separated names' },
      { key: 'focus', label: 'Focus Areas', placeholder: 'pricing, features, marketing' },
    ],
  },
  market_research: {
    label: 'Market Research',
    description: 'Evaluate market size, segments, and opportunity landscape',
    fields: [
      { key: 'market', label: 'Market', placeholder: 'Target market or industry' },
      { key: 'region', label: 'Region', placeholder: 'US, EU, Global' },
      { key: 'question', label: 'Research Question', placeholder: 'What do you want to know?', type: 'textarea' },
    ],
  },
  trend_detection: {
    label: 'Trend Detection',
    description: 'Identify emerging trends, signals, and shifts in a domain',
    fields: [
      { key: 'domain', label: 'Domain', placeholder: 'AI, fintech, healthcare...' },
      { key: 'signals', label: 'Signal Sources', placeholder: 'news, patents, funding' },
      { key: 'horizon', label: 'Time Horizon', placeholder: '3 months, 1 year' },
    ],
  },
};

const TEMPLATE_IDS = Object.keys(TEMPLATES) as TemplateId[];

import { API_BASE } from '../lib/config';
import { getToken } from '../lib/auth';

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ─── Result Card ────────────────────────────────────────────────────────────

function ResultCard({ label, value }: { label: string; value: unknown }) {
  const display = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  const isLong = display.length > 200;

  return (
    <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
      <div className="text-xs font-medium text-nc-accent mb-2 capitalize">
        {label.replace(/_/g, ' ')}
      </div>
      <div className={`text-sm text-nc-text ${isLong ? 'whitespace-pre-wrap font-mono text-xs' : ''}`}>
        {display}
      </div>
    </div>
  );
}

// ─── History Item ───────────────────────────────────────────────────────────

function HistoryItem({ run, isActive, onClick }: { run: ResearchRun; isActive: boolean; onClick: () => void }) {
  const tpl = TEMPLATES[run.template];
  const statusDot =
    run.status === 'completed' ? 'bg-nc-green' :
    run.status === 'running' ? 'bg-nc-yellow animate-pulse' :
    'bg-nc-red';

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
        isActive ? 'bg-nc-accent/20' : 'hover:bg-nc-surface-2'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDot}`} />
        <span className="text-xs text-nc-text truncate">{tpl?.label || run.template}</span>
      </div>
      <div className="text-[10px] text-nc-text-dim mt-0.5 pl-3.5">
        {new Date(run.started_at).toLocaleString()}
      </div>
    </button>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function ResearchTab() {
  const [template, setTemplate] = useState<TemplateId>('social_intelligence');
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ResearchRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const config = TEMPLATES[template];

  // Reset inputs when template changes
  useEffect(() => {
    setInputs({});
    setResult(null);
    setError(null);
  }, [template]);

  // Load history on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/research/history`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : { runs: [] })
      .then(data => setHistory(Array.isArray(data.runs) ? data.runs : []))
      .catch(() => setHistory([]));
  }, []);

  const runResearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/research/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ template, inputs }),
      });
      if (!res.ok) throw new Error(`Research failed (${res.status})`);
      const data = await res.json();
      setResult(data.result || data);
      // Add to history
      const run: ResearchRun = {
        id: data.run_id || crypto.randomUUID(),
        template,
        inputs: { ...inputs },
        status: 'completed',
        result: data.result || data,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      };
      setHistory(prev => [run, ...prev]);
      setActiveRunId(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [template, inputs]);

  const selectHistoryRun = (run: ResearchRun) => {
    setActiveRunId(run.id);
    setTemplate(run.template);
    setInputs(run.inputs);
    setResult(run.result);
    setError(run.status === 'failed' ? 'Run failed' : null);
  };

  const resultEntries = result ? Object.entries(result) : [];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-nc-border">
        <h1 className="text-lg font-semibold text-nc-text">Research</h1>
        <p className="text-xs text-nc-text-dim">Run research workflows — social intel, competitors, markets, trends</p>
      </div>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* History sidebar */}
        <aside className="w-56 shrink-0 border-r border-nc-border overflow-y-auto p-2 space-y-0.5">
          <div className="text-[10px] font-medium text-nc-text-dim uppercase tracking-wider px-3 py-1">
            History
          </div>
          {history.length === 0 && (
            <div className="text-xs text-nc-text-dim px-3 py-4 text-center">No runs yet</div>
          )}
          {history.map(run => (
            <HistoryItem
              key={run.id}
              run={run}
              isActive={activeRunId === run.id}
              onClick={() => selectHistoryRun(run)}
            />
          ))}
        </aside>

        {/* Main panel */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Template selector */}
          <div>
            <label className="text-xs font-medium text-nc-text-dim block mb-2">Template</label>
            <div className="flex gap-2 flex-wrap">
              {TEMPLATE_IDS.map(id => (
                <button
                  key={id}
                  onClick={() => setTemplate(id)}
                  className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                    template === id
                      ? 'bg-nc-accent/20 text-nc-accent'
                      : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2 border border-nc-border'
                  }`}
                >
                  {TEMPLATES[id].label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-nc-text-dim mt-1.5">{config.description}</p>
          </div>

          {/* Dynamic input form */}
          <div className="grid grid-cols-1 gap-4 max-w-xl">
            {config.fields.map(field => (
              <div key={field.key}>
                <label className="text-xs font-medium text-nc-text-dim block mb-1">{field.label}</label>
                {field.type === 'textarea' ? (
                  <textarea
                    value={inputs[field.key] || ''}
                    onChange={e => setInputs(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder}
                    rows={3}
                    className="w-full bg-nc-surface border border-nc-border rounded-lg px-3 py-2 text-sm text-nc-text placeholder:text-nc-text-dim/50 focus:outline-none focus:border-nc-accent resize-none"
                  />
                ) : (
                  <input
                    type="text"
                    value={inputs[field.key] || ''}
                    onChange={e => setInputs(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder}
                    className="w-full bg-nc-surface border border-nc-border rounded-lg px-3 py-2 text-sm text-nc-text placeholder:text-nc-text-dim/50 focus:outline-none focus:border-nc-accent"
                  />
                )}
              </div>
            ))}
          </div>

          {/* Run button */}
          <button
            onClick={runResearch}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-colors bg-nc-accent text-white hover:bg-nc-accent/80 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Running...' : 'Run Research'}
          </button>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-nc-text-dim animate-pulse">
              <span className="w-2 h-2 rounded-full bg-nc-yellow animate-pulse" />
              Executing research workflow...
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-nc-red/10 border border-nc-red/30 rounded-lg px-4 py-3 text-sm text-nc-red">
              {error}
            </div>
          )}

          {/* Results */}
          {result && !loading && (
            <div className="space-y-4">
              <div className="text-xs font-medium text-nc-text-dim uppercase tracking-wider">Results</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {resultEntries.map(([key, value]) => (
                  <ResultCard key={key} label={key} value={value} />
                ))}
              </div>
              {resultEntries.length === 0 && (
                <div className="text-sm text-nc-text-dim">No result data returned</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
