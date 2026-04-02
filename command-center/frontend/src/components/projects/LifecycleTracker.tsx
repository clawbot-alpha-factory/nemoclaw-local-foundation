'use client';

import { useState, useEffect } from 'react';
import { fetchProjectLifecycle, advanceProjectStage } from '@/lib/projects-api';
import type { ProjectLifecycle, LifecycleStage } from '@/lib/projects-api';

interface Props {
  projectId: string;
}

const STAGE_COLORS: Record<string, string> = {
  pending: 'bg-zinc-500',
  active: 'bg-blue-500 animate-pulse',
  completed: 'bg-emerald-500',
  skipped: 'bg-zinc-600',
};

export default function LifecycleTracker({ projectId }: Props) {
  const [lifecycle, setLifecycle] = useState<ProjectLifecycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);

  useEffect(() => {
    fetchProjectLifecycle(projectId)
      .then(setLifecycle)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId]);

  async function handleAdvance() {
    setAdvancing(true);
    try {
      const updated = await advanceProjectStage(projectId);
      setLifecycle(updated);
    } catch (err) {
      console.error('Advance error:', err);
    } finally {
      setAdvancing(false);
    }
  }

  if (loading) return <div className="text-sm text-nc-text-dim animate-pulse p-4">Loading lifecycle...</div>;
  if (!lifecycle) return <div className="text-sm text-nc-text-dim p-4">No lifecycle data</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-nc-text">Lifecycle</h4>
          <div className="text-xs text-nc-text-dim">Current: {lifecycle.current_stage}</div>
        </div>
        <button
          onClick={handleAdvance}
          disabled={advancing}
          className="px-3 py-1.5 text-xs bg-nc-accent text-white rounded-lg hover:bg-nc-accent/80 disabled:opacity-50 transition-colors"
        >{advancing ? 'Advancing...' : 'Advance Stage'}</button>
      </div>

      {/* Stage pipeline */}
      <div className="flex items-center gap-1">
        {lifecycle.stages.map((stage, i) => (
          <div key={stage.stage} className="flex items-center flex-1">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${STAGE_COLORS[stage.status]}`} />
                <span className={`text-xs font-medium ${
                  stage.status === 'active' ? 'text-nc-text' : 'text-nc-text-dim'
                } capitalize`}>
                  {stage.stage.replace(/_/g, ' ')}
                </span>
              </div>
              {stage.entered_at && (
                <div className="text-[10px] text-nc-text-dim ml-5">
                  {new Date(stage.entered_at).toLocaleDateString()}
                </div>
              )}
              {stage.gate_passed && (
                <div className="text-[10px] text-nc-green ml-5">Gate passed</div>
              )}
            </div>
            {i < lifecycle.stages.length - 1 && (
              <div className={`w-6 h-px mx-1 ${
                stage.status === 'completed' ? 'bg-emerald-500' : 'bg-zinc-600'
              }`} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
