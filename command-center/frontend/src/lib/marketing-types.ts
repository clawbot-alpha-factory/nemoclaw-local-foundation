// Marketing types for Zara's content factory

export type ContentStatus = 'queued' | 'in_progress' | 'review' | 'approved' | 'published' | 'failed';
export type VideoPipelineStage = 'scripted' | 'voiceover' | 'rendering' | 'editing' | 'complete' | 'failed';
export type Platform = 'instagram' | 'tiktok' | 'youtube' | 'linkedin' | 'twitter';

export interface ContentProject {
  id: string;
  skill_id: string;
  skill_name: string;
  title: string;
  status: ContentStatus;
  platform: Platform | null;
  agent_id: string;
  created_at: string;
  completed_at: string | null;
  output_path: string | null;
}

export interface VideoJob {
  id: string;
  title: string;
  agent_character: string;
  stage: VideoPipelineStage;
  script_skill: string | null;
  heygen_job_id: string | null;
  capcut_project_id: string | null;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface SocialPost {
  id: string;
  platform: Platform;
  content: string;
  media_url: string | null;
  scheduled_at: string;
  published_at: string | null;
  status: 'scheduled' | 'published' | 'failed' | 'draft';
  engagement: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
  } | null;
}

export interface ContentMetrics {
  total_pieces: number;
  published_count: number;
  in_progress_count: number;
  total_views: number;
  total_engagement: number;
  avg_viral_score: number;
  by_platform: Record<Platform, {
    count: number;
    views: number;
    engagement: number;
  }>;
}

export interface ContentPipelineResponse {
  projects: ContentProject[];
  total: number;
}

export interface VideoQueueResponse {
  jobs: VideoJob[];
  total: number;
}

export interface SocialCalendarResponse {
  posts: SocialPost[];
  total: number;
}
