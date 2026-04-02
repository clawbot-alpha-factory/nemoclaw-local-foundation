// Marketing API client — Zara's content factory
import type {
  ContentPipelineResponse,
  VideoQueueResponse,
  SocialCalendarResponse,
  ContentMetrics,
} from './marketing-types';

import { API_BASE } from './config';
const API = `${API_BASE}/api/marketing`;

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: headers() });
  if (!res.ok) throw new Error(`Marketing API error: ${res.status}`);
  return res.json();
}

export async function fetchContentPipeline(status?: string): Promise<ContentPipelineResponse> {
  const params = status ? `?status=${status}` : '';
  return get(`${API}/pipeline${params}`);
}

export async function fetchVideoQueue(): Promise<VideoQueueResponse> {
  return get(`${API}/videos`);
}

export async function fetchSocialCalendar(platform?: string): Promise<SocialCalendarResponse> {
  const params = platform ? `?platform=${platform}` : '';
  return get(`${API}/calendar${params}`);
}

export async function fetchContentPerformance(): Promise<ContentMetrics> {
  return get(`${API}/performance`);
}
