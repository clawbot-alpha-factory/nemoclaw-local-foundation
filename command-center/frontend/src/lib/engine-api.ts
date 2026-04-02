/**
 * NemoClaw Engine API Client
 * Fetches data from all engine endpoints.
 */

import { API_BASE } from './config';

const BASE = API_BASE;

function getToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('cc-token') || '';
  }
  return '';
}

async function fetchApi<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const token = getToken();
  const opts: RequestInit = {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Autonomous
export const fetchLoopStatus = () => fetchApi<any>('/api/autonomous/loop/status');
export const fetchScheduler = () => fetchApi<any>('/api/autonomous/scheduler');
export const fetchDashboard = () => fetchApi<any>('/api/autonomous/dashboard');
export const fetchDailySummary = () => fetchApi<any>('/api/autonomous/daily-summary');
export const fetchDecisionLog = () => fetchApi<any>('/api/autonomous/decision-log');
export const fetchImprovementTasks = () => fetchApi<any>('/api/autonomous/improvement-tasks');
export const fetchPromptOptimization = () => fetchApi<any>('/api/autonomous/prompt-optimization');
export const startLoop = () => fetchApi<any>('/api/autonomous/loop/start', 'POST');
export const stopLoop = () => fetchApi<any>('/api/autonomous/loop/stop', 'POST');
export const runSelfAudit = () => fetchApi<any>('/api/autonomous/self-audit', 'POST');

// Revenue
export const fetchPipeline = () => fetchApi<any>('/api/revenue/pipeline');
export const fetchCatalog = () => fetchApi<any>('/api/revenue/catalog');
export const fetchEvents = () => fetchApi<any>('/api/revenue/events');
export const fetchAttribution = () => fetchApi<any>('/api/revenue/attribution');

// Lifecycle
export const fetchOnboarding = () => fetchApi<any>('/api/lifecycle/onboarding');
export const fetchHealth = () => fetchApi<any>('/api/lifecycle/health');

// Bridges
export const fetchBridges = () => fetchApi<any>('/api/bridges/status');

// Skills
export const fetchSkillWiring = () => fetchApi<any>('/api/skill-wiring/stats');
export const fetchChains = () => fetchApi<any>('/api/skill-wiring/chains');
