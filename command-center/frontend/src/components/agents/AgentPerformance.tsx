'use client';

import { useState, useEffect } from 'react';
import { fetchAgentPerformance } from '@/lib/agents-api';
import type { AgentPerformance as AgentPerformanceType, PerformanceDimension } from '@/lib/agents-api';

interface Props {
  agentId: string;
}

const ALERT_COLORS: Record<string, string> = {
  normal: 'bg-emerald-500/20 text-emerald-400',
  watch: 'bg-amber-500/20 text-amber-400',
  warning: 'bg-orange-500/20 text-orange-400',
  critical: 'bg-red-500/20 text-red-400',
};

const TREND_ICONS: Record<string, string> = {
  up: '↑',
  down: '↓',
  stable: '→',
};

const TREND_COLORS: Record<string, string> = {
  up: 'text-emerald-400',
  down: 'text-red-400',
  stable: 'text-zinc-400',
};

function DimensionBar({ dim }: { dim: PerformanceDimension }) {
  const percent = dim.score * 100;
  const barColor =
    percent >= 80 ? 'bg-emerald-500' :
    percent >= 60 ? 'bg-amber-500' :
    percent >= 40 ? 'bg-orange-500' :
    'bg-red-500';

  return (
    <div className="flex items-center gap-3">
      <div className="w-28 text-xs text-zinc-300 capitalize">{dim.dimension.replace(/_/g, ' ')}</div>
      <div className="flex-1 h-2 bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${percent}%` }} />
      </div>
      <div className="w-12 text-right text-xs text-zinc-300">{percent.toFixed(0)}%</div>
      <span className={`text-xs ${TREND_COLORS[dim.trend]}`}>{TREND_ICONS[dim.trend]}</span>
      <span className="w-8 text-[10px] text-zinc-500 text-right">n={dim.sample_count}</span>
    </div>
  );
}

export default function AgentPerformance({ agentId }: Props) {
  const [data, setData] = useState<AgentPerformanceType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgentPerformance(agentId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [agentId]);

  if (loading) return <div className="text-sm text-zinc-500 animate-pulse p-4">Loading performance...</div>;
  if (!data) return <div className="text-sm text-zinc-500 p-4">Unable to load performance data</div>;

  const compositePercent = data.composite_score * 100;

  return (
    <div className="p-4 space-y-4">
      {/* Composite score */}
      <div className="flex items-center gap-4 bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
        <div className="text-center">
          <div className="text-3xl font-bold text-zinc-100">{compositePercent.toFixed(0)}</div>
          <div className="text-[10px] text-zinc-400">Composite</div>
        </div>
        <div className="flex-1">
          <div className="h-3 bg-zinc-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                compositePercent >= 80 ? 'bg-emerald-500' :
                compositePercent >= 60 ? 'bg-amber-500' : 'bg-red-500'
              }`}
              style={{ width: `${compositePercent}%` }}
            />
          </div>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${ALERT_COLORS[data.alert_level]}`}>
          {data.alert_level}
        </span>
      </div>

      {/* Dimensions */}
      <div className="bg-zinc-800/30 rounded-lg p-4 border border-zinc-700/30 space-y-3">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Performance Dimensions</h4>
        {data.dimensions.map((dim) => (
          <DimensionBar key={dim.dimension} dim={dim} />
        ))}
      </div>

      {/* Last updated */}
      <div className="text-[10px] text-zinc-500 text-right">
        Last updated: {new Date(data.last_updated).toLocaleString()}
      </div>
    </div>
  );
}
