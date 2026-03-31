'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchLoopStatus, fetchScheduler, fetchDashboard, fetchDailySummary,
  fetchDecisionLog, fetchImprovementTasks, fetchPromptOptimization,
  startLoop, stopLoop, runSelfAudit, fetchPipeline, fetchBridges,
  fetchSkillWiring, fetchChains, fetchEvents,
} from '../lib/engine-api';

const SECTIONS = ['Overview', 'Pipeline', 'Loop', 'Scheduler', 'Audit', 'Decisions'] as const;
type Section = (typeof SECTIONS)[number];

const BADGE: Record<string, string> = {
  running: 'bg-green-100 text-green-800',
  stopped: 'bg-red-100 text-red-800',
  conservative: 'bg-blue-100 text-blue-800',
  balanced: 'bg-yellow-100 text-yellow-800',
  aggressive: 'bg-red-100 text-red-800',
  true: 'bg-green-100 text-green-800',
  false: 'bg-nc-surface-2 text-nc-text-dim',
};

function Badge({ value }: { value: string }) {
  const cls = BADGE[value.toLowerCase()] || 'bg-nc-surface-2 text-nc-text-dim';
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{value}</span>;
}

function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-nc-surface border border-nc-border rounded-lg p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-nc-text mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div>
      <div className="text-2xl font-bold text-nc-text">{value}</div>
      <div className="text-xs text-nc-text-dim">{label}</div>
      {sub && <div className="text-xs text-nc-accent mt-0.5">{sub}</div>}
    </div>
  );
}

export default function ExecutionTab() {
  const [section, setSection] = useState<Section>('Overview');
  const [loop, setLoop] = useState<any>(null);
  const [scheduler, setScheduler] = useState<any>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [decisions, setDecisions] = useState<any>(null);
  const [tasks, setTasks] = useState<any>(null);
  const [pipeline, setPipeline] = useState<any>(null);
  const [bridges, setBridges] = useState<any>(null);
  const [wiring, setWiring] = useState<any>(null);
  const [chains, setChains] = useState<any>(null);
  const [events, setEvents] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [l, s, d, sm, dec, t, p, b, w, ch, ev] = await Promise.allSettled([
        fetchLoopStatus(), fetchScheduler(), fetchDashboard(), fetchDailySummary(),
        fetchDecisionLog(), fetchImprovementTasks(), fetchPipeline(), fetchBridges(),
        fetchSkillWiring(), fetchChains(), fetchEvents(),
      ]);
      if (l.status === 'fulfilled') setLoop(l.value);
      if (s.status === 'fulfilled') setScheduler(s.value);
      if (d.status === 'fulfilled') setDashboard(d.value);
      if (sm.status === 'fulfilled') setSummary(sm.value);
      if (dec.status === 'fulfilled') setDecisions(dec.value);
      if (t.status === 'fulfilled') setTasks(t.value);
      if (p.status === 'fulfilled') setPipeline(p.value);
      if (b.status === 'fulfilled') setBridges(b.value);
      if (w.status === 'fulfilled') setWiring(w.value);
      if (ch.status === 'fulfilled') setChains(ch.value);
      if (ev.status === 'fulfilled') setEvents(ev.value);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const handleStartLoop = async () => { await startLoop(); load(); };
  const handleStopLoop = async () => { await stopLoop(); load(); };
  const handleAudit = async () => { await runSelfAudit(); load(); };

  if (loading && !dashboard) return <div className="p-6 text-nc-text-dim">Loading engine data...</div>;
  if (error) return <div className="p-6 text-nc-red">Error: {error}</div>;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-5 pb-3 border-b border-nc-border bg-nc-surface flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nc-text">Execution Engine</h1>
          <p className="text-xs text-nc-text-dim mt-0.5">Autonomous operation dashboard</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge value={loop?.running ? 'Running' : 'Stopped'} />
          <Badge value={loop?.mode || 'unknown'} />
          {!loop?.running ? (
            <button onClick={handleStartLoop} className="px-3 py-1.5 bg-nc-green text-white rounded text-xs font-medium hover:opacity-90">Start Loop</button>
          ) : (
            <button onClick={handleStopLoop} className="px-3 py-1.5 bg-nc-red text-white rounded text-xs font-medium hover:opacity-90">Stop Loop</button>
          )}
          <button onClick={handleAudit} className="px-3 py-1.5 bg-nc-accent text-white rounded text-xs font-medium hover:opacity-90">Run Audit</button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="px-6 py-2 border-b border-nc-border bg-nc-surface flex gap-1">
        {SECTIONS.map(s => (
          <button key={s} onClick={() => setSection(s)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${section === s ? 'bg-nc-accent text-white' : 'text-nc-text-dim hover:bg-nc-surface-2'}`}>
            {s}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {section === 'Overview' && <OverviewSection summary={summary} dashboard={dashboard} bridges={bridges} wiring={wiring} loop={loop} events={events} />}
        {section === 'Pipeline' && <PipelineSection pipeline={pipeline} />}
        {section === 'Loop' && <LoopSection loop={loop} />}
        {section === 'Scheduler' && <SchedulerSection scheduler={scheduler} />}
        {section === 'Audit' && <AuditSection tasks={tasks} />}
        {section === 'Decisions' && <DecisionsSection decisions={decisions} />}
      </div>
    </div>
  );
}

function OverviewSection({ summary, dashboard, bridges, wiring, loop, events }: any) {
  const pipe = dashboard?.pipeline || {};
  const rev = dashboard?.revenue || {};
  const health = dashboard?.health || {};
  const mapping = wiring?.mapping || {};

  return (
    <div className="space-y-4">
      {/* Key metrics row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card title="Pipeline"><Stat label="Total deals" value={pipe.total_deals ?? 0} sub={`$${pipe.total_value ?? 0}`} /></Card>
        <Card title="Revenue"><Stat label="Total" value={`$${rev.total_revenue ?? 0}`} sub={`ROI: ${rev.overall_roi ?? 'N/A'}`} /></Card>
        <Card title="Loop"><Stat label="Ticks" value={loop?.tick_count ?? 0} sub={`${loop?.executions_this_hour ?? 0}/hr`} /></Card>
        <Card title="Skills"><Stat label="Mapped" value={mapping.unique_skills_mapped ?? 0} sub={`${mapping.shared_skills ?? 0} shared`} /></Card>
        <Card title="Bridges"><Stat label="Enabled" value={Object.values(bridges?.bridges || {}).filter((b: any) => b.enabled).length} sub={`of ${Object.keys(bridges?.bridges || {}).length}`} /></Card>
        <Card title="Health"><Stat label="At risk" value={health.at_risk ?? 0} sub={`Avg: ${health.avg_health ?? 'N/A'}`} /></Card>
      </div>

      {/* Daily summary */}
      {summary && (
        <Card title="Daily Summary">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><span className="text-nc-text-dim">Date:</span> <span className="font-medium">{summary.date}</span></div>
            <div><span className="text-nc-text-dim">Pipeline:</span> <span className="font-medium">${summary.pipeline_value}</span></div>
            <div><span className="text-nc-text-dim">Forecast:</span> <span className="font-medium">${summary.weighted_forecast}</span></div>
            <div><span className="text-nc-text-dim">Stale deals:</span> <span className="font-medium">{summary.stale_deals}</span></div>
            <div><span className="text-nc-text-dim">At risk:</span> <span className="font-medium">{summary.at_risk_clients}</span></div>
            <div><span className="text-nc-text-dim">Experiments:</span> <span className="font-medium">{summary.experiments_running}</span></div>
            <div><span className="text-nc-text-dim">Spend:</span> <span className="font-medium">${summary.daily_spend}</span></div>
          </div>
        </Card>
      )}

      {/* Events */}
      {events?.stats && (
        <Card title="Event Bus">
          <div className="text-sm">
            <span className="text-nc-text-dim">Total events:</span>{' '}
            <span className="font-medium">{events.stats.total_events}</span>
            <span className="text-nc-text-dim ml-4">Types registered:</span>{' '}
            <span className="font-medium">{events.stats.registered_types}</span>
          </div>
        </Card>
      )}
    </div>
  );
}

function PipelineSection({ pipeline }: any) {
  if (!pipeline) return <div className="text-nc-text-dim">No pipeline data</div>;
  const stages = pipeline.stages || {};
  const deals = pipeline.deals || [];

  return (
    <div className="space-y-4">
      <Card title="Pipeline Stages">
        <div className="flex gap-2 flex-wrap">
          {Object.entries(stages).map(([stage, count]: any) => (
            <div key={stage} className="px-3 py-2 bg-nc-surface-2 rounded text-center min-w-[100px]">
              <div className="text-lg font-bold text-nc-text">{count}</div>
              <div className="text-xs text-nc-text-dim">{stage}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card title={`Deals (${deals.length})`}>
        {deals.length === 0 ? <div className="text-sm text-nc-text-dim">No deals</div> : (
          <div className="space-y-2">
            {deals.map((d: any) => (
              <div key={d.deal_id} className="flex items-center justify-between p-2 bg-nc-surface-2 rounded text-sm">
                <div><span className="font-medium">{d.lead_name}</span> <span className="text-nc-text-dim">({d.deal_id})</span></div>
                <div className="flex items-center gap-3">
                  <Badge value={d.stage} />
                  <span className="font-medium">${d.value}</span>
                  <span className="text-nc-text-dim text-xs">{d.days_in_stage}d</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
      {pipeline.conversion_rates && (
        <Card title="Conversion Rates">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            {Object.entries(pipeline.conversion_rates).map(([k, v]: any) => (
              <div key={k} className="p-2 bg-nc-surface-2 rounded">
                <div className="font-medium">{v}%</div>
                <div className="text-xs text-nc-text-dim">{k}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function LoopSection({ loop }: any) {
  if (!loop) return <div className="text-nc-text-dim">No loop data</div>;
  return (
    <div className="space-y-4">
      <Card title="Autonomous Loop">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Status" value={loop.running ? 'Running' : 'Stopped'} />
          <Stat label="Mode" value={loop.mode} />
          <Stat label="Ticks" value={loop.tick_count} />
          <Stat label="Executions/hr" value={`${loop.executions_this_hour}/${loop.max_per_hour}`} />
        </div>
        {loop.started_at && <div className="mt-2 text-xs text-nc-text-dim">Started: {loop.started_at}</div>}
      </Card>
      {loop.recent_executions?.length > 0 && (
        <Card title="Recent Executions">
          <div className="space-y-1">
            {loop.recent_executions.map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-nc-surface-2 rounded text-xs">
                <span className="font-medium">{r.skill_id || r.trigger}</span>
                <div className="flex items-center gap-2">
                  <Badge value={r.result} />
                  <span className="text-nc-text-dim">{r.agent}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function SchedulerSection({ scheduler }: any) {
  if (!scheduler) return <div className="text-nc-text-dim">No scheduler data</div>;
  return (
    <Card title={`Scheduled Jobs (${scheduler.total_jobs})`}>
      <div className="text-xs mb-2"><Badge value={scheduler.running ? 'Running' : 'Stopped'} /></div>
      <div className="space-y-2">
        {(scheduler.jobs || []).map((j: any) => (
          <div key={j.name} className="flex items-center justify-between p-2 bg-nc-surface-2 rounded text-sm">
            <div>
              <span className="font-medium">{j.name}</span>
              {j.description && <span className="text-nc-text-dim ml-2 text-xs">{j.description}</span>}
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span>every {j.interval_human}</span>
              <span className="text-nc-text-dim">runs: {j.run_count}</span>
              {j.last_error && <span className="text-nc-red">{j.last_error}</span>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function AuditSection({ tasks }: any) {
  if (!tasks) return <div className="text-nc-text-dim">No audit data</div>;
  const stats = tasks.stats || {};
  const items = tasks.tasks || [];

  return (
    <div className="space-y-4">
      <Card title="Self-Improvement">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Total audits" value={stats.total_audits ?? 0} />
          <Stat label="Pending tasks" value={stats.pending_tasks ?? 0} />
          <Stat label="Avg score" value={`${stats.avg_score ?? 0}/100`} />
        </div>
      </Card>
      {items.length > 0 && (
        <Card title={`Improvement Tasks (${items.length})`}>
          <div className="space-y-1">
            {items.map((t: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-nc-surface-2 rounded text-xs">
                <span>{t.title}</span>
                <div className="flex items-center gap-2">
                  <Badge value={t.priority} />
                  <span className="text-nc-text-dim">{t.agent}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function DecisionsSection({ decisions }: any) {
  const log = decisions?.log || [];
  if (log.length === 0) return <div className="text-nc-text-dim">No decisions yet. Start the autonomous loop to see decision chains.</div>;
  return (
    <Card title={`Decision Log (${log.length})`}>
      <div className="space-y-1">
        {log.map((d: any, i: number) => (
          <div key={i} className="flex items-center justify-between p-2 bg-nc-surface-2 rounded text-xs">
            <div>
              <span className="text-nc-text-dim">trigger:</span> <span className="font-medium">{d.trigger}</span>
              <span className="text-nc-text-dim ml-2">skill:</span> <span className="font-medium">{d.skill_id}</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge value={d.result} />
              {d.cost > 0 && <span className="text-nc-text-dim">${d.cost}</span>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
