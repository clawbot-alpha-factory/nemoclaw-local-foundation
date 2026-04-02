'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchContentPipeline,
  fetchVideoQueue,
  fetchSocialCalendar,
  fetchContentPerformance,
} from '../lib/marketing-api';
import type {
  ContentProject,
  VideoJob,
  SocialPost,
  ContentMetrics,
  Platform,
} from '../lib/marketing-types';

type SubView = 'pipeline' | 'videos' | 'calendar' | 'performance' | 'assets';

const SUB_VIEWS: { id: SubView; label: string }[] = [
  { id: 'pipeline', label: 'Content Pipeline' },
  { id: 'videos', label: 'Video Factory' },
  { id: 'calendar', label: 'Social Calendar' },
  { id: 'performance', label: 'Performance' },
  { id: 'assets', label: 'Assets' },
];

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-slate-500/20 text-slate-400',
  in_progress: 'bg-blue-500/20 text-blue-400',
  review: 'bg-amber-500/20 text-amber-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  published: 'bg-nc-green/20 text-nc-green',
  failed: 'bg-nc-red/20 text-nc-red',
  scripted: 'bg-purple-500/20 text-purple-400',
  voiceover: 'bg-indigo-500/20 text-indigo-400',
  rendering: 'bg-blue-500/20 text-blue-400',
  editing: 'bg-amber-500/20 text-amber-400',
  complete: 'bg-nc-green/20 text-nc-green',
  scheduled: 'bg-blue-500/20 text-blue-400',
  draft: 'bg-slate-500/20 text-slate-400',
};

const PLATFORM_ICONS: Record<Platform, string> = {
  instagram: '📸',
  tiktok: '🎵',
  youtube: '📺',
  linkedin: '💼',
  twitter: '🐦',
};

function Badge({ label }: { label: string }) {
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_COLORS[label] || 'bg-nc-surface-2 text-nc-text-dim'}`}>
      {label.replace('_', ' ')}
    </span>
  );
}

function LoadingState() {
  return <div className="text-center py-8 text-sm text-nc-text-dim animate-pulse">Loading...</div>;
}

// ─── Content Pipeline ────────────────────────────────────────────────────────

function PipelineView() {
  const [projects, setProjects] = useState<ContentProject[] | null>(null);

  useEffect(() => {
    fetchContentPipeline()
      .then(({ projects: p }) => setProjects(p))
      .catch(() => setProjects([]));
  }, []);

  if (!projects) return <LoadingState />;

  const grouped = {
    in_progress: projects.filter(p => p.status === 'in_progress'),
    review: projects.filter(p => p.status === 'review'),
    queued: projects.filter(p => p.status === 'queued'),
    published: projects.filter(p => p.status === 'published').slice(0, 10),
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
          <div className="text-2xl font-bold text-blue-400">{grouped.in_progress.length}</div>
          <div className="text-[10px] text-nc-text-dim">In Progress</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
          <div className="text-2xl font-bold text-amber-400">{grouped.review.length}</div>
          <div className="text-[10px] text-nc-text-dim">In Review</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
          <div className="text-2xl font-bold text-slate-400">{grouped.queued.length}</div>
          <div className="text-[10px] text-nc-text-dim">Queued</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
          <div className="text-2xl font-bold text-nc-green">{grouped.published.length}</div>
          <div className="text-[10px] text-nc-text-dim">Published</div>
        </div>
      </div>

      {/* Active content */}
      <div className="space-y-2">
        {[...grouped.in_progress, ...grouped.review, ...grouped.queued].map((p) => (
          <div key={p.id} className="bg-nc-surface rounded-lg border border-nc-border p-3 flex items-center gap-3">
            {p.platform && <span className="text-lg">{PLATFORM_ICONS[p.platform]}</span>}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-nc-text truncate">{p.title}</div>
              <div className="text-[10px] text-nc-text-dim">{p.skill_name} &middot; {p.agent_id}</div>
            </div>
            <Badge label={p.status} />
            <div className="text-[10px] text-nc-text-dim">{new Date(p.created_at).toLocaleDateString()}</div>
          </div>
        ))}
        {projects.length === 0 && (
          <div className="text-center py-8 text-sm text-nc-text-dim">No content in pipeline</div>
        )}
      </div>
    </div>
  );
}

// ─── Video Factory ───────────────────────────────────────────────────────────

function VideoFactoryView() {
  const [jobs, setJobs] = useState<VideoJob[] | null>(null);

  useEffect(() => {
    fetchVideoQueue()
      .then(({ jobs: j }) => setJobs(j))
      .catch(() => setJobs([]));
  }, []);

  if (!jobs) return <LoadingState />;

  const stages: VideoPipelineStage[] = ['scripted', 'voiceover', 'rendering', 'editing', 'complete'];
  type VideoPipelineStage = 'scripted' | 'voiceover' | 'rendering' | 'editing' | 'complete' | 'failed';

  return (
    <div className="space-y-4">
      {/* Pipeline stages */}
      <div className="flex gap-2">
        {stages.map((stage, i) => {
          const count = jobs.filter(j => j.stage === stage).length;
          return (
            <div key={stage} className="flex-1 bg-nc-surface rounded-lg border border-nc-border p-3 text-center">
              <div className="text-lg font-bold text-nc-text">{count}</div>
              <div className="text-[10px] text-nc-text-dim capitalize">{stage}</div>
              {i < stages.length - 1 && <div className="text-nc-text-dim text-xs mt-1">&rarr;</div>}
            </div>
          );
        })}
      </div>

      {/* Job list */}
      <div className="space-y-2">
        {jobs.map((j) => (
          <div key={j.id} className="bg-nc-surface rounded-lg border border-nc-border p-3 flex items-center gap-3">
            <span className="text-lg">🎬</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-nc-text truncate">{j.title}</div>
              <div className="text-[10px] text-nc-text-dim">
                {j.agent_character}
                {j.duration_seconds && ` &middot; ${j.duration_seconds}s`}
              </div>
            </div>
            <Badge label={j.stage} />
            <div className="text-[10px] text-nc-text-dim">{new Date(j.updated_at).toLocaleTimeString()}</div>
          </div>
        ))}
        {jobs.length === 0 && (
          <div className="text-center py-8 text-sm text-nc-text-dim">No videos in production</div>
        )}
      </div>
    </div>
  );
}

// ─── Social Calendar ─────────────────────────────────────────────────────────

function SocialCalendarView() {
  const [posts, setPosts] = useState<SocialPost[] | null>(null);
  const [platformFilter, setPlatformFilter] = useState<Platform | ''>('');

  const load = useCallback(async () => {
    try {
      const { posts: p } = await fetchSocialCalendar(platformFilter || undefined);
      setPosts(p);
    } catch {
      setPosts([]);
    }
  }, [platformFilter]);

  useEffect(() => { load(); }, [load]);

  if (!posts) return <LoadingState />;

  const platforms: Platform[] = ['instagram', 'tiktok', 'youtube', 'linkedin', 'twitter'];

  return (
    <div className="space-y-4">
      {/* Platform filter */}
      <div className="flex gap-1">
        <button
          onClick={() => setPlatformFilter('')}
          className={`px-2 py-1 text-xs rounded-lg transition-colors ${
            !platformFilter ? 'bg-nc-accent/20 text-nc-accent' : 'text-nc-text-dim hover:bg-nc-surface-2'
          }`}
        >All</button>
        {platforms.map((p) => (
          <button
            key={p}
            onClick={() => setPlatformFilter(p)}
            className={`px-2 py-1 text-xs rounded-lg transition-colors ${
              platformFilter === p ? 'bg-nc-accent/20 text-nc-accent' : 'text-nc-text-dim hover:bg-nc-surface-2'
            }`}
          >{PLATFORM_ICONS[p]} {p}</button>
        ))}
      </div>

      {/* Post list */}
      <div className="space-y-2">
        {posts.map((p) => (
          <div key={p.id} className="bg-nc-surface rounded-lg border border-nc-border p-3">
            <div className="flex items-start gap-3">
              <span className="text-lg">{PLATFORM_ICONS[p.platform]}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-nc-text line-clamp-2">{p.content}</div>
                <div className="flex items-center gap-3 mt-2 text-[10px] text-nc-text-dim">
                  <Badge label={p.status} />
                  <span>{new Date(p.scheduled_at).toLocaleString()}</span>
                  {p.engagement && (
                    <span>{p.engagement.views} views &middot; {p.engagement.likes} likes</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
        {posts.length === 0 && (
          <div className="text-center py-8 text-sm text-nc-text-dim">No scheduled posts</div>
        )}
      </div>
    </div>
  );
}

// ─── Performance ─────────────────────────────────────────────────────────────

function PerformanceView() {
  const [metrics, setMetrics] = useState<ContentMetrics | null>(null);

  useEffect(() => {
    fetchContentPerformance()
      .then(setMetrics)
      .catch(() => setMetrics({
        total_pieces: 0, published_count: 0, in_progress_count: 0,
        total_views: 0, total_engagement: 0, avg_viral_score: 0,
        by_platform: {} as any,
      }));
  }, []);

  if (!metrics) return <LoadingState />;

  const platforms = Object.entries(metrics.by_platform) as [Platform, { count: number; views: number; engagement: number }][];

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <div className="text-xs text-nc-text-dim">Total Pieces</div>
          <div className="text-2xl font-bold text-nc-text">{metrics.total_pieces}</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <div className="text-xs text-nc-text-dim">Published</div>
          <div className="text-2xl font-bold text-nc-green">{metrics.published_count}</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <div className="text-xs text-nc-text-dim">Total Views</div>
          <div className="text-2xl font-bold text-nc-text">{metrics.total_views.toLocaleString()}</div>
        </div>
        <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
          <div className="text-xs text-nc-text-dim">Avg Viral Score</div>
          <div className="text-2xl font-bold text-nc-accent">{metrics.avg_viral_score.toFixed(1)}</div>
        </div>
      </div>

      {/* Per-platform */}
      <div className="bg-nc-surface rounded-lg border border-nc-border p-4">
        <h3 className="text-sm font-medium text-nc-text mb-4">By Platform</h3>
        <div className="grid grid-cols-5 gap-4">
          {platforms.map(([platform, data]) => (
            <div key={platform} className="text-center">
              <div className="text-2xl mb-1">{PLATFORM_ICONS[platform]}</div>
              <div className="text-sm font-medium text-nc-text capitalize">{platform}</div>
              <div className="text-xs text-nc-text-dim">{data.count} pieces</div>
              <div className="text-xs text-nc-text-dim">{data.views.toLocaleString()} views</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Assets ──────────────────────────────────────────────────────────────────

function AssetsView() {
  return (
    <div className="text-center py-12">
      <div className="text-4xl mb-3">🎨</div>
      <div className="text-sm text-nc-text-dim">Asset browser coming soon</div>
      <div className="text-xs text-nc-text-dim mt-1">Thumbnails, hooks, scripts from cnt-* skills</div>
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function MarketingTab() {
  const [view, setView] = useState<SubView>('pipeline');

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-nc-border">
        <div className="flex items-center gap-2">
          <span className="text-lg">🎬</span>
          <div>
            <h1 className="text-lg font-semibold text-nc-text">Marketing — Zara&apos;s Content Factory</h1>
            <p className="text-xs text-nc-text-dim">Content pipeline, video production, social media, analytics</p>
          </div>
        </div>
      </div>

      {/* Sub-nav */}
      <div className="px-6 py-2 border-b border-nc-border flex gap-1">
        {SUB_VIEWS.map((sv) => (
          <button
            key={sv.id}
            onClick={() => setView(sv.id)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              view === sv.id
                ? 'bg-nc-accent/20 text-nc-accent'
                : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
            }`}
          >{sv.label}</button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {view === 'pipeline' && <PipelineView />}
        {view === 'videos' && <VideoFactoryView />}
        {view === 'calendar' && <SocialCalendarView />}
        {view === 'performance' && <PerformanceView />}
        {view === 'assets' && <AssetsView />}
      </div>
    </div>
  );
}
