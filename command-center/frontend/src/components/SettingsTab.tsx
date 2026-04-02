'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  fetchSettings,
  fetchToken,
  setTheme,
  fetchSystemInfo,
  updateBrainInterval,
  fetchApiKeys,
  testApiKey,
  fetchModelLibrary,
  fetchRoutingRules,
  fetchBridgeStatus,
  runBridgeHealthCheck,
} from '../lib/settings-api';
import type {
  Settings,
  ActiveToken,
  SystemInfo,
  ThemePreference,
  ApiKeyInfo,
  ModelAlias,
  RoutingRule,
  BridgeInfo as SettingsBridgeInfo,
} from '../lib/settings-api';

const SECTIONS = ['Token Setup', 'API Keys', 'Model Library', 'Tools & Bridges', 'NVIDIA NIM', 'Theme', 'Brain Settings', 'System Info', 'About'] as const;
type Section = (typeof SECTIONS)[number];

const VERSION = '1.0.0';
const REPO_LINK = 'https://github.com/nemoclaw/command-center';

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className || 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" strokeWidth={2} />
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" strokeWidth={2} />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className || 'w-4 h-4'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <polyline points="20 6 9 17 4 12" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SunIcon({ className }: { className?: string }) {
  return (
    <svg className={className || 'w-5 h-5'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="5" strokeWidth={2} />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeWidth={2} strokeLinecap="round" />
    </svg>
  );
}

function MoonIcon({ className }: { className?: string }) {
  return (
    <svg className={className || 'w-5 h-5'} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function SettingsTab() {
  const [activeSection, setActiveSection] = useState<Section>('Token Setup');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [token, setToken] = useState<ActiveToken | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [currentTheme, setCurrentTheme] = useState<'light' | 'dark'>('light');
  const [brainInterval, setBrainInterval] = useState<number>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [applySuccess, setApplySuccess] = useState(false);
  const [themeSaving, setThemeSaving] = useState(false);
  const [intervalSaving, setIntervalSaving] = useState(false);
  const [intervalSaved, setIntervalSaved] = useState(false);

  // New section state (hoisted to avoid hooks-in-conditional)
  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [apiKeysLoaded, setApiKeysLoaded] = useState(false);
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [models, setModels] = useState<ModelAlias[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [routingRules, setRoutingRules] = useState<RoutingRule[]>([]);
  const [defaultAlias, setDefaultAlias] = useState('');
  const [bridges, setBridges] = useState<SettingsBridgeInfo[]>([]);
  const [bridgesLoaded, setBridgesLoaded] = useState(false);
  const [showFull, setShowFull] = useState(false);

  const loadAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsData, tokenData, sysData] = await Promise.all([
        fetchSettings().catch(() => null),
        fetchToken().catch(() => null),
        fetchSystemInfo().catch(() => null),
      ]);

      if (settingsData) {
        setSettings(settingsData);
        setCurrentTheme(settingsData.theme || 'light');
        setBrainInterval(settingsData.intervals?.brain_interval || 30);
      }
      if (tokenData) {
        setToken(tokenData);
      }
      if (sysData) {
        setSystemInfo(sysData);
      }

      const storedTheme = localStorage.getItem('cc-theme') as 'light' | 'dark' | null;
      if (storedTheme) {
        setCurrentTheme(storedTheme);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  const handleCopyToken = useCallback(async () => {
    if (!token?.token) return;
    try {
      await navigator.clipboard.writeText(token.token);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = token.token;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  }, [token]);

  const handleApplyToken = useCallback(() => {
    if (!token?.token) return;
    localStorage.setItem('cc-token', token.token);
    setApplySuccess(true);
    setTimeout(() => setApplySuccess(false), 3000);
  }, [token]);

  const handleThemeToggle = useCallback(async () => {
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    setThemeSaving(true);
    try {
      await setTheme(newTheme);
      setCurrentTheme(newTheme);
      localStorage.setItem('cc-theme', newTheme);
      document.documentElement.classList.toggle('dark', newTheme === 'dark');
    } catch (err) {
      console.error('Failed to set theme:', err);
    } finally {
      setThemeSaving(false);
    }
  }, [currentTheme]);

  const handleIntervalChange = useCallback((value: number) => {
    setBrainInterval(value);
  }, []);

  const handleIntervalSave = useCallback(async () => {
    setIntervalSaving(true);
    setIntervalSaved(false);
    try {
      await updateBrainInterval(brainInterval);
      setIntervalSaved(true);
      setTimeout(() => setIntervalSaved(false), 2000);
    } catch (err) {
      console.error('Failed to update brain interval:', err);
    } finally {
      setIntervalSaving(false);
    }
  }, [brainInterval]);

  const maskedToken = useMemo(() => {
    if (!token?.token) return '—';
    const t = token.token;
    if (t.length <= 12) return t;
    return t.slice(0, 6) + '•'.repeat(Math.min(t.length - 12, 20)) + t.slice(-6);
  }, [token]);

  const summaryCards = useMemo(() => {
    const tokenStatus = token?.token ? 'Active' : 'Not Set';
    const tokenBadge = token?.token
      ? 'bg-green-100 text-green-800'
      : 'bg-red-100 text-red-800';
    const localToken = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
    const localTokenStatus = localToken ? 'Applied' : 'Missing';
    const localTokenBadge = localToken
      ? 'bg-green-100 text-green-800'
      : 'bg-yellow-100 text-yellow-800';

    return { tokenStatus, tokenBadge, localTokenStatus, localTokenBadge };
  }, [token]);

  const renderSectionNav = () => (
    <div className="flex flex-wrap gap-1 mb-6 bg-nc-surface rounded-lg p-1">
      {SECTIONS.map((section) => (
        <button
          key={section}
          onClick={() => setActiveSection(section)}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
            activeSection === section
              ? 'bg-nc-accent text-white shadow-sm'
              : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
          }`}
        >
          {section}
        </button>
      ))}
    </div>
  );

  const renderSummaryCards = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
      <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
        <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-1">Server Token</div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${summaryCards.tokenBadge}`}>
            {summaryCards.tokenStatus}
          </span>
        </div>
      </div>
      <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
        <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-1">Local Token</div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${summaryCards.localTokenBadge}`}>
            {summaryCards.localTokenStatus}
          </span>
        </div>
      </div>
      <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
        <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-1">Theme</div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            {currentTheme === 'light' ? '☀️ Light' : '🌙 Dark'}
          </span>
        </div>
      </div>
    </div>
  );

  const renderTokenSetup = () => {
    return (
      <div className="space-y-6">
        <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-nc-text mb-1">Active Token</h3>
          <p className="text-sm text-nc-text-dim mb-4">
            This is the authentication token from the server. Copy and apply it to authenticate all API requests.
          </p>

          {token?.token ? (
            <div className="space-y-4">
              <div className="bg-nc-surface-2 border border-nc-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-nc-text-dim uppercase tracking-wide">Token Value</span>
                  <button
                    onClick={() => setShowFull(!showFull)}
                    className="text-xs text-nc-accent hover:underline"
                  >
                    {showFull ? 'Hide' : 'Reveal'}
                  </button>
                </div>
                <code className="block text-sm text-nc-text break-all font-mono leading-relaxed">
                  {showFull ? token.token : maskedToken}
                </code>
              </div>

              {token.created_at && (
                <div className="flex items-center gap-4 text-xs text-nc-text-dim">
                  <span>Created: {new Date(token.created_at).toLocaleString()}</span>
                  {token.expires_at && (
                    <span>Expires: {new Date(token.expires_at).toLocaleString()}</span>
                  )}
                  {token.expires_at === null && (
                    <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-800 text-xs">
                      No Expiry
                    </span>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleCopyToken}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm font-medium text-nc-text hover:bg-nc-border transition-colors"
                >
                  {copySuccess ? (
                    <>
                      <CheckIcon className="w-4 h-4 text-green-600" />
                      <span className="text-green-600">Copied!</span>
                    </>
                  ) : (
                    <>
                      <CopyIcon className="w-4 h-4" />
                      <span>Copy Token</span>
                    </>
                  )}
                </button>

                <button
                  onClick={handleApplyToken}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                >
                  {applySuccess ? (
                    <>
                      <CheckIcon className="w-4 h-4" />
                      <span>Applied to localStorage!</span>
                    </>
                  ) : (
                    <span>Copy & Apply</span>
                  )}
                </button>
              </div>

              {applySuccess && (
                <div className="bg-green-100 border border-green-200 rounded-lg p-3">
                  <p className="text-sm text-green-800">
                    ✅ Token saved to <code className="font-mono text-xs bg-green-200 px-1 rounded">localStorage[&apos;cc-token&apos;]</code>. All API requests will now use this token automatically.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-yellow-100 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-800">
                ⚠️ No token found on the server. The API may not require authentication, or the token endpoint is unavailable.
              </p>
            </div>
          )}
        </div>

        <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-nc-text mb-2">Auto-Set Instructions</h3>
          <p className="text-sm text-nc-text-dim mb-4">
            Instead of manually copying the token, you can use the &quot;Copy & Apply&quot; button above which will:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-sm text-nc-text">
            <li>Fetch the current active token from the server</li>
            <li>Store it in <code className="font-mono text-xs bg-nc-surface-2 px-1.5 py-0.5 rounded border border-nc-border">localStorage</code> under the key <code className="font-mono text-xs bg-nc-surface-2 px-1.5 py-0.5 rounded border border-nc-border">cc-token</code></li>
            <li>All subsequent API calls will include it in the <code className="font-mono text-xs bg-nc-surface-2 px-1.5 py-0.5 rounded border border-nc-border">Authorization: Bearer</code> header</li>
          </ol>
          <div className="mt-4 bg-blue-100 border border-blue-200 rounded-lg p-3">
            <p className="text-sm text-blue-800">
              💡 <strong>Tip:</strong> If you&apos;re running NemoClaw locally, the token should auto-apply. Click &quot;Copy & Apply&quot; if API calls return 401 errors.
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderTheme = () => (
    <div className="space-y-6">
      <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-nc-text mb-1">Appearance</h3>
        <p className="text-sm text-nc-text-dim mb-6">
          Choose between light and dark mode. Your preference is saved in localStorage.
        </p>

        <div className="flex items-center gap-6">
          <button
            onClick={handleThemeToggle}
            disabled={themeSaving}
            className="relative inline-flex items-center h-10 w-20 rounded-full transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-nc-accent focus:ring-offset-2"
            style={{
              backgroundColor: currentTheme === 'dark' ? 'var(--nc-accent, #6366f1)' : '#e2e8f0',
            }}
          >
            <span
              className={`inline-flex items-center justify-center w-8 h-8 rounded-full bg-white shadow-md transform transition-transform duration-300 ${
                currentTheme === 'dark' ? 'translate-x-11' : 'translate-x-1'
              }`}
            >
              {currentTheme === 'dark' ? (
                <MoonIcon className="w-4 h-4 text-nc-accent" />
              ) : (
                <SunIcon className="w-4 h-4 text-yellow-500" />
              )}
            </span>
          </button>

          <div>
            <span className="text-sm font-medium text-nc-text">
              {currentTheme === 'light' ? 'Light Mode' : 'Dark Mode'}
            </span>
            <p className="text-xs text-nc-text-dim">
              {themeSaving ? 'Saving...' : 'Click the toggle to switch'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          className={`bg-nc-surface border-2 rounded-xl p-6 cursor-pointer transition-all ${
            currentTheme === 'light' ? 'border-nc-accent shadow-md' : 'border-nc-border'
          }`}
          onClick={() => {
            if (currentTheme !== 'light') handleThemeToggle();
          }}
        >
          <div className="flex items-center gap-3 mb-3">
            <SunIcon className="w-6 h-6 text-yellow-500" />
            <span className="font-semibold text-nc-text">Light</span>
            {currentTheme === 'light' && (
              <span className="ml-auto px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Active
              </span>
            )}
          </div>
          <div className="space-y-2">
            <div className="h-3 bg-white rounded w-full border" />
            <div className="h-3 bg-white rounded w-3/4 border" />
            <div className="h-3 bg-white rounded w-1/2 border" />
          </div>
        </div>

        <div
          className={`bg-nc-surface border-2 rounded-xl p-6 cursor-pointer transition-all ${
            currentTheme === 'dark' ? 'border-nc-accent shadow-md' : 'border-nc-border'
          }`}
          onClick={() => {
            if (currentTheme !== 'dark') handleThemeToggle();
          }}
        >
          <div className="flex items-center gap-3 mb-3">
            <MoonIcon className="w-6 h-6 text-nc-accent" />
            <span className="font-semibold text-nc-text">Dark</span>
            {currentTheme === 'dark' && (
              <span className="ml-auto px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                Active
              </span>
            )}
          </div>
          <div className="space-y-2">
            <div className="h-3 bg-nc-surface-2 rounded w-full" />
            <div className="h-3 bg-nc-surface-2 rounded w-3/4" />
            <div className="h-3 bg-nc-surface-2 rounded w-1/2" />
          </div>
        </div>
      </div>
    </div>
  );

  const renderBrainSettings = () => (
    <div className="space-y-6">
      <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-nc-text mb-1">Auto-Insight Interval</h3>
        <p className="text-sm text-nc-text-dim mb-6">
          Configure how frequently the Brain generates automatic insights. Lower values mean more frequent analysis.
        </p>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-nc-text-dim">Interval</span>
            <span className="text-2xl font-bold text-nc-accent">{brainInterval}s</span>
          </div>

          <input
            type="range"
            min={5}
            max={300}
            step={5}
            value={brainInterval}
            onChange={(e) => handleIntervalChange(Number(e.target.value))}
            className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-nc-accent bg-nc-surface-2"
          />

          <div className="flex justify-between text-xs text-nc-text-dim">
            <span>5s (Aggressive)</span>
            <span>60s (Normal)</span>
            <span>300s (Relaxed)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-4">
            {[
              { label: 'Aggressive', value: 10, desc: 'Real-time analysis' },
              { label: 'Normal', value: 60, desc: 'Balanced performance' },
              { label: 'Relaxed', value: 180, desc: 'Low resource usage' },
            ].map((preset) => (
              <button
                key={preset.label}
                onClick={() => handleIntervalChange(preset.value)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  brainInterval === preset.value
                    ? 'border-nc-accent bg-nc-accent/5'
                    : 'border-nc-border bg-nc-surface-2 hover:border-nc-accent/50'
                }`}
              >
                <span className="text-sm font-medium text-nc-text">{preset.label}</span>
                <span className="block text-xs text-nc-text-dim mt-0.5">{preset.desc} — {preset.value}s</span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleIntervalSave}
              disabled={intervalSaving}
              className="inline-flex items-center gap-2 px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {intervalSaving ? (
                <span>Saving...</span>
              ) : intervalSaved ? (
                <>
                  <CheckIcon className="w-4 h-4" />
                  <span>Saved!</span>
                </>
              ) : (
                <span>Save Interval</span>
              )}
            </button>

            {intervalSaved && (
              <span className="text-sm text-green-800 bg-green-100 px-2 py-0.5 rounded-full">
                ✓ Updated
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  const renderSystemInfo = () => (
    <div className="space-y-6">
      {systemInfo ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">Python Version</div>
            <div className="text-lg font-semibold text-nc-text font-mono">{systemInfo.python_version}</div>
          </div>

          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">Node Version</div>
            <div className="text-lg font-semibold text-nc-text font-mono">{systemInfo.node_version}</div>
          </div>

          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">Uptime</div>
            <div className="text-lg font-semibold text-nc-text">
              {systemInfo.uptime_human || (typeof systemInfo.uptime === 'object'
                ? `${(systemInfo.uptime as any).hours || 0}h ${(systemInfo.uptime as any).seconds || 0}s`
                : `${systemInfo.uptime}s`)}
            </div>
            <div className="text-xs text-nc-text-dim mt-1">
              {typeof systemInfo.uptime === 'number' ? `${systemInfo.uptime.toLocaleString()}s total` : `${(systemInfo.uptime as any).seconds || 0}s total`}
            </div>
          </div>

          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">Git Branch</div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold text-nc-text font-mono">{systemInfo.git.branch}</span>
              {systemInfo.git.dirty && (
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                  dirty
                </span>
              )}
            </div>
          </div>

          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">Git Commit</div>
            <div className="text-lg font-semibold text-nc-text font-mono truncate" title={systemInfo.git.commit}>
              {systemInfo.git.commit.slice(0, 12)}
            </div>
            <div className="text-xs text-nc-text-dim mt-1 font-mono truncate">{systemInfo.git.commit}</div>
          </div>

          <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
            <div className="text-xs text-nc-text-dim uppercase tracking-wide mb-2">API Status</div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-lg font-semibold text-nc-text">Connected</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-nc-surface border border-nc-border rounded-xl p-8 text-center">
          <p className="text-nc-text-dim">Loading system information...</p>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={loadAllData}
          className="inline-flex items-center gap-2 px-4 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm font-medium text-nc-text hover:bg-nc-border transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Refresh
        </button>
      </div>
    </div>
  );

  const renderNvidiaNim = () => {
    const freeModels = [
      { name: 'Nemotron Embed 1B v2', type: 'Embedding', status: 'active', desc: '26-language semantic embeddings (2048 dim, 8192 tokens)', endpoint: 'integrate.api.nvidia.com/v1/embeddings', cost: 'Free tier' },
      { name: 'Nemotron Rerank 1B v2', type: 'Reranking', status: 'active', desc: 'Cross-encoder reranking for search quality', endpoint: 'integrate.api.nvidia.com/v1/ranking', cost: 'Free tier' },
      { name: 'Content Safety 4B', type: 'Safety', status: 'active', desc: 'Policy-aware content safety classification', endpoint: 'integrate.api.nvidia.com/v1/chat/completions', cost: 'Free tier' },
      { name: 'GLiNER PII Detection', type: 'PII', status: 'active', desc: 'Regex fallback active. NIM container needed for full 55+ entity detection.', endpoint: 'Self-hosted NIM or regex fallback', cost: 'Free (regex) / NIM container' },
      { name: 'Nemotron Nano 9B v2', type: 'Chat LLM', status: 'active', desc: 'Hybrid Mamba-Transformer, Tier 1 routing candidate', endpoint: 'integrate.api.nvidia.com/v1/chat/completions', cost: 'Free tier' },
      { name: 'Nemotron 3 Nano 30B A3B', type: 'Chat LLM', status: 'active', desc: '30B MoE (3.5B active), 1M context, Tier 2 candidate', endpoint: 'integrate.api.nvidia.com/v1/chat/completions', cost: 'Free tier' },
    ];
    const futureModels = [
      { name: 'NVIDIA AI Enterprise', type: 'Platform', status: 'planned', desc: 'Production-grade NIM hosting, no rate limits', cost: '$4,500/GPU/year', needed: 'When free tier 40 RPM becomes bottleneck' },
      { name: 'NeMo Guardrails (self-hosted)', type: 'Safety', status: 'planned', desc: 'Full guardrails pipeline with custom policies', cost: 'Free (self-hosted)', needed: 'When outbound volume exceeds free API limits' },
      { name: 'Nemotron 3 Super 120B', type: 'Chat LLM', status: 'planned', desc: '120B MoE (12B active), premium reasoning tier', cost: 'Paid NIM API', needed: 'When quality needs exceed Sonnet/GPT-5.4' },
      { name: 'NVIDIA Riva (ASR/TTS)', type: 'Voice', status: 'planned', desc: 'Real-time speech recognition + synthesis', cost: 'AI Enterprise license', needed: 'When live voice agent interactions needed' },
    ];

    return (
      <div className="space-y-6">
        <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-nc-text">NVIDIA NIM — Free Tier (Active)</h3>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">6 models connected</span>
          </div>
          <p className="text-sm text-nc-text-secondary mb-1">Endpoint: integrate.api.nvidia.com/v1</p>
          <p className="text-sm text-nc-text-secondary mb-4">Limits: 5,000 credits / 40 RPM / Trial service</p>
          <div className="space-y-3">
            {freeModels.map((m) => (
              <div key={m.name} className="flex items-center justify-between p-3 bg-nc-surface-2 rounded-lg border border-nc-border/50">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-400" />
                  <div>
                    <span className="text-sm font-medium text-nc-text">{m.name}</span>
                    <span className="ml-2 px-2 py-0.5 rounded text-xs bg-nc-accent/10 text-nc-accent">{m.type}</span>
                    <p className="text-xs text-nc-text-secondary mt-0.5">{m.desc}</p>
                  </div>
                </div>
                <span className="text-xs text-green-400 font-medium">{m.cost}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-nc-text">Upgrade Path — Future Subscriptions</h3>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">Not yet needed</span>
          </div>
          <p className="text-sm text-nc-text-secondary mb-4">These become relevant as NemoClaw scales beyond free tier limits.</p>
          <div className="space-y-3">
            {futureModels.map((m) => (
              <div key={m.name} className="flex items-center justify-between p-3 bg-nc-surface-2 rounded-lg border border-nc-border/50 opacity-60">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-yellow-400" />
                  <div>
                    <span className="text-sm font-medium text-nc-text">{m.name}</span>
                    <span className="ml-2 px-2 py-0.5 rounded text-xs bg-yellow-500/10 text-yellow-400">{m.type}</span>
                    <p className="text-xs text-nc-text-secondary mt-0.5">{m.desc}</p>
                    <p className="text-xs text-yellow-400/70 mt-0.5">Trigger: {m.needed}</p>
                  </div>
                </div>
                <span className="text-xs text-yellow-400 font-medium">{m.cost}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderAbout = () => (
    <div className="space-y-6">
      <div className="bg-nc-surface border border-nc-border rounded-xl p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-nc-accent/10 mb-4">
          <svg className="w-8 h-8 text-nc-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-nc-text mb-1">NemoClaw Command Center</h2>
        <p className="text-nc-text-dim mb-4">AI Agent Orchestration & Monitoring</p>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-100 text-blue-800 text-sm font-medium mb-6">
          v{VERSION}
        </div>

        <div className="max-w-md mx-auto space-y-3 text-sm text-nc-text-dim text-left">
          <p>
            NemoClaw Command Center is the central hub for managing, monitoring, and orchestrating
            AI agents, skills, and workflows. It provides real-time insights, brain analysis, and
            comprehensive system management.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
          <h4 className="text-sm font-semibold text-nc-text mb-3">Quick Links</h4>
          <div className="space-y-2">
            <a
              href={REPO_LINK}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-nc-accent hover:underline"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              GitHub Repository
            </a>
            <a
              href={`${REPO_LINK}/issues`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-nc-accent hover:underline"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" strokeWidth={2} />
                <path d="M12 8v4M12 16h.01" strokeWidth={2} strokeLinecap="round" />
              </svg>
              Report an Issue
            </a>
            <a
              href={`${REPO_LINK}/wiki`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-nc-accent hover:underline"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Documentation
            </a>
          </div>
        </div>

        <div className="bg-nc-surface border border-nc-border rounded-xl p-5">
          <h4 className="text-sm font-semibold text-nc-text mb-3">Build Info</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-nc-text-dim">Version</span>
              <span className="text-nc-text font-mono">{VERSION}</span>
            </div>
            {systemInfo?.git && (
              <>
                <div className="flex justify-between">
                  <span className="text-nc-text-dim">Branch</span>
                  <span className="text-nc-text font-mono">{systemInfo.git.branch}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-nc-text-dim">Commit</span>
                  <span className="text-nc-text font-mono">{systemInfo.git.commit.slice(0, 8)}</span>
                </div>
              </>
            )}
            <div className="flex justify-between">
              <span className="text-nc-text-dim">API Base</span>
              <span className="text-nc-text font-mono text-xs">http://127.0.0.1:8100</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // ─── API Keys Section ─────────────────────────────────────────────────────

  const renderApiKeys = () => {
    if (!apiKeysLoaded) {
      setApiKeysLoaded(true);
      fetchApiKeys().then(({ keys }) => setApiKeys(keys)).catch(console.error);
      return <div className="text-sm text-nc-text-dim animate-pulse p-4">Loading API keys...</div>;
    }
    if (apiKeys.length === 0) {
      return <div className="text-sm text-nc-text-dim p-4">No API keys configured</div>;
    }

    const statusDot = (s: string) =>
      s === 'connected' ? 'bg-green-500' : s === 'missing' ? 'bg-zinc-500' : 'bg-red-500';

    return (
      <div className="space-y-4">
        <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
          <h3 className="text-lg font-semibold text-nc-text mb-4">API Keys & Connections</h3>
          <div className="space-y-3">
            {apiKeys.map((k) => (
              <div key={k.provider} className="flex items-center gap-3 bg-nc-surface-2 rounded-lg p-3">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusDot(k.status)}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-nc-text">{k.provider}</div>
                  <div className="text-xs text-nc-text-dim font-mono">
                    {k.masked_key || 'Not configured'}
                  </div>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                  k.status === 'connected' ? 'bg-green-100 text-green-800' :
                  k.status === 'missing' ? 'bg-zinc-100 text-zinc-600' :
                  'bg-red-100 text-red-800'
                }`}>{k.status}</span>
                {k.configured && (
                  <button
                    onClick={async () => {
                      setTestingKey(k.provider);
                      try {
                        const result = await testApiKey(k.provider);
                        setApiKeys(prev => prev.map(key =>
                          key.provider === k.provider
                            ? { ...key, status: result.success ? 'connected' : 'invalid' }
                            : key
                        ));
                      } catch { /* ignore */ }
                      setTestingKey(null);
                    }}
                    disabled={testingKey === k.provider}
                    className="px-2 py-1 text-xs bg-nc-surface border border-nc-border rounded-lg hover:bg-nc-border transition-colors disabled:opacity-50"
                  >{testingKey === k.provider ? 'Testing...' : 'Test'}</button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ─── Model Library Section ──────────────────────────────────────────────────

  const renderModelLibrary = () => {
    if (!modelsLoaded) {
      setModelsLoaded(true);
      Promise.all([
        fetchModelLibrary().catch(() => ({ aliases: [] })),
        fetchRoutingRules().catch(() => ({ rules: [], default_alias: '' })),
      ]).then(([modelData, ruleData]) => {
        setModels(modelData.aliases);
        setRoutingRules(ruleData.rules);
        setDefaultAlias(ruleData.default_alias);
      });
      return <div className="text-sm text-nc-text-dim animate-pulse p-4">Loading model library...</div>;
    }
    if (models.length === 0) {
      return <div className="text-sm text-nc-text-dim p-4">No models configured</div>;
    }

    return (
      <div className="space-y-6">
        {/* Model aliases */}
        <div className="bg-nc-surface border border-nc-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-nc-border">
            <h3 className="text-lg font-semibold text-nc-text">9-Alias Model Library</h3>
            <p className="text-xs text-nc-text-dim mt-1">LLM aliases from routing-config.yaml (L-003)</p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-nc-border bg-nc-surface-2">
                <th className="text-left p-3 text-nc-text-dim font-medium text-xs">Alias</th>
                <th className="text-left p-3 text-nc-text-dim font-medium text-xs">Provider</th>
                <th className="text-left p-3 text-nc-text-dim font-medium text-xs">Model</th>
                <th className="text-right p-3 text-nc-text-dim font-medium text-xs">Cost/Call</th>
                <th className="text-right p-3 text-nc-text-dim font-medium text-xs">Max Tokens</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.alias} className="border-b border-nc-border/50 hover:bg-nc-surface-2">
                  <td className="p-3">
                    <span className="font-mono text-nc-accent text-xs">{m.alias}</span>
                    {m.alias === defaultAlias && (
                      <span className="ml-1 text-[10px] px-1 py-0.5 rounded bg-blue-100 text-blue-800">default</span>
                    )}
                  </td>
                  <td className="p-3 text-nc-text text-xs">{m.provider}</td>
                  <td className="p-3 text-nc-text-dim text-xs font-mono">{m.model}</td>
                  <td className="p-3 text-right text-nc-text-dim text-xs">${m.cost_per_call.toFixed(4)}</td>
                  <td className="p-3 text-right text-nc-text-dim text-xs">{m.max_tokens.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Routing rules */}
        <div className="bg-nc-surface border border-nc-border rounded-xl overflow-hidden">
          <div className="p-4 border-b border-nc-border">
            <h3 className="text-sm font-semibold text-nc-text">Routing Rules</h3>
          </div>
          <div className="p-4 grid grid-cols-2 gap-2">
            {routingRules.map((r) => (
              <div key={r.task_class} className="flex items-center justify-between bg-nc-surface-2 rounded-lg px-3 py-2">
                <span className="text-xs text-nc-text">{r.task_class}</span>
                <span className="text-xs font-mono text-nc-accent">{r.alias}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ─── Tools & Bridges Section ────────────────────────────────────────────────

  const renderToolsBridges = () => {
    if (!bridgesLoaded) {
      setBridgesLoaded(true);
      fetchBridgeStatus().then(({ bridges: b }) => setBridges(b)).catch(console.error);
      return <div className="text-sm text-nc-text-dim animate-pulse p-4">Loading bridges...</div>;
    }
    if (bridges.length === 0) {
      return <div className="text-sm text-nc-text-dim p-4">No bridges configured</div>;
    }

    const statusColors: Record<string, string> = {
      connected: 'bg-green-500',
      mocked: 'bg-amber-500',
      error: 'bg-red-500',
      unconfigured: 'bg-zinc-500',
    };

    return (
      <div className="bg-nc-surface border border-nc-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-nc-text mb-4">Tools & Bridges</h3>
        <div className="grid grid-cols-2 gap-3">
          {bridges.map((b) => (
            <div key={b.id} className="bg-nc-surface-2 rounded-lg p-3 border border-nc-border/50">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${statusColors[b.status] || 'bg-zinc-500'}`} />
                <span className="text-sm font-medium text-nc-text">{b.name}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-nc-text-dim capitalize">{b.status}</span>
                <span className="text-nc-text-dim">{b.call_count} calls</span>
              </div>
              <div className="flex items-center gap-1 mt-2">
                {b.has_api_key && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-green-100 text-green-800">Key</span>
                )}
                {b.enabled && (
                  <span className="text-[10px] px-1 py-0.5 rounded bg-blue-100 text-blue-800">Enabled</span>
                )}
                <button
                  onClick={() => {
                    runBridgeHealthCheck(b.id)
                      .then(() => fetchBridgeStatus().then(({ bridges: updated }) => setBridges(updated)))
                      .catch(console.error);
                  }}
                  className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-nc-surface border border-nc-border hover:bg-nc-border transition-colors text-nc-text-dim"
                >Health Check</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderActiveSection = () => {
    switch (activeSection) {
      case 'Token Setup':
        return renderTokenSetup();
      case 'API Keys':
        return renderApiKeys();
      case 'Model Library':
        return renderModelLibrary();
      case 'Tools & Bridges':
        return renderToolsBridges();
      case 'NVIDIA NIM':
        return renderNvidiaNim();
      case 'Theme':
        return renderTheme();
      case 'Brain Settings':
        return renderBrainSettings();
      case 'System Info':
        return renderSystemInfo();
      case 'About':
        return renderAbout();
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-nc-surface-2 rounded w-48" />
          <div className="h-10 bg-nc-surface-2 rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-nc-surface-2 rounded-xl" />
            ))}
          </div>
          <div className="h-64 bg-nc-surface-2 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-nc-bg min-h-full">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-nc-text">Settings</h1>
        <p className="text-sm text-nc-text-dim mt-1">
          Configure your NemoClaw Command Center preferences, tokens, and system settings.
        </p>
      </div>

      {error && (
        <div className="mb-6 bg-red-100 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-red-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" strokeWidth={2} />
              <path d="M15 9l-6 6M9 9l6 6" strokeWidth={2} strokeLinecap="round" />
            </svg>
            <span className="text-sm text-red-800 font-medium">Error loading settings</span>
          </div>
          <p className="text-xs text-red-800 mt-1">{error}</p>
          <button
            onClick={loadAllData}
            className="mt-2 text-xs text-red-800 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {renderSummaryCards()}
      {renderSectionNav()}
      {renderActiveSection()}
    </div>
  );
}