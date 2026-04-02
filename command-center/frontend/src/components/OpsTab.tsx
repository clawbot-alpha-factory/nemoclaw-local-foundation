'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  fetchDashboard,
  fetchTasks,
  createTask,
  updateTask,
  fetchBudget,
  fetchActivity,
} from '../lib/ops-api';
import type {
  DashboardData,
  Task,
  TaskListResponse,
  TaskCreateInput,
  TaskUpdateInput,
  TaskFilters,
  BudgetBreakdown,
  ProviderBudget,
  ActivityEntry,
  ActivityFeedResponse,
} from '../lib/ops-api';

const TABS = ['Dashboard', 'Tasks', 'Finance'] as const;
type TabName = (typeof TABS)[number];

const STATUS_OPTIONS = ['pending', 'in_progress', 'completed', 'failed', 'cancelled'] as const;
const PRIORITY_OPTIONS = ['critical', 'high', 'medium', 'low'] as const;

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-red-100 text-red-800',
};

const PRIORITY_BADGE: Record<string, string> = {
  critical: 'bg-red-100 text-red-800',
  high: 'bg-yellow-100 text-yellow-800',
  medium: 'bg-blue-100 text-blue-800',
  low: 'bg-green-100 text-green-800',
};

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCurrency(val: number | null | undefined): string {
  if (val == null) return '$0.00';
  return `$${val.toFixed(2)}`;
}

function percentOf(spent: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min((spent / total) * 100, 100);
}

export default function OpsTab() {
  const [activeTab, setActiveTab] = useState<TabName>('Dashboard');
  const [error, setError] = useState<string | null>(null);

  // Dashboard state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [dashLoading, setDashLoading] = useState(false);

  // Tasks state
  const [taskResponse, setTaskResponse] = useState<TaskListResponse | null>(null);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [taskFilters, setTaskFilters] = useState<TaskFilters>({ page: 1, page_size: 20 });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<TaskCreateInput>({ title: '', description: '', priority: 'medium' });
  const [creating, setCreating] = useState(false);
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);

  // Finance state
  const [budget, setBudget] = useState<BudgetBreakdown | null>(null);
  const [financeLoading, setFinanceLoading] = useState(false);

  const loadDashboard = useCallback(async () => {
    setDashLoading(true);
    setError(null);
    try {
      const [dash, actFeed] = await Promise.all([
        fetchDashboard(),
        fetchActivity(1, 20),
      ]);
      setDashboard(dash);
      setActivities(actFeed.activities);
    } catch (e: any) {
      setError(e.message || 'Failed to load dashboard');
    } finally {
      setDashLoading(false);
    }
  }, []);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    setError(null);
    try {
      const res = await fetchTasks(taskFilters);
      setTaskResponse(res);
    } catch (e: any) {
      setError(e.message || 'Failed to load tasks');
    } finally {
      setTasksLoading(false);
    }
  }, [taskFilters]);

  const loadFinance = useCallback(async () => {
    setFinanceLoading(true);
    setError(null);
    try {
      const res = await fetchBudget();
      setBudget(res);
    } catch (e: any) {
      setError(e.message || 'Failed to load finance data');
    } finally {
      setFinanceLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'Dashboard') loadDashboard();
    else if (activeTab === 'Tasks') loadTasks();
    else if (activeTab === 'Finance') loadFinance();
  }, [activeTab, loadDashboard, loadTasks, loadFinance]);

  const handleCreateTask = useCallback(async () => {
    if (!createForm.title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createTask(createForm);
      setShowCreateModal(false);
      setCreateForm({ title: '', description: '', priority: 'medium' });
      loadTasks();
    } catch (e: any) {
      setError(e.message || 'Failed to create task');
    } finally {
      setCreating(false);
    }
  }, [createForm, loadTasks]);

  const handleQuickStatus = useCallback(
    async (taskId: string, newStatus: Task['status']) => {
      setUpdatingTaskId(taskId);
      setError(null);
      try {
        await updateTask(taskId, { status: newStatus });
        loadTasks();
      } catch (e: any) {
        setError(e.message || 'Failed to update task');
      } finally {
        setUpdatingTaskId(null);
      }
    },
    [loadTasks]
  );

  const handleFilterChange = useCallback((key: keyof TaskFilters, value: string) => {
    setTaskFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
      page: 1,
    }));
  }, []);

  const totalPages = useMemo(() => {
    if (!taskResponse) return 1;
    return Math.max(1, Math.ceil(taskResponse.total / (taskResponse.page_size || 20)));
  }, [taskResponse]);

  const spendProjection = useMemo(() => {
    if (!budget) return 0;
    const now = new Date();
    const dayOfMonth = now.getDate();
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    if (dayOfMonth === 0) return budget.total_spent_usd;
    return (budget.total_spent_usd / dayOfMonth) * daysInMonth;
  }, [budget]);

  const costAlerts = useMemo(() => {
    if (!budget) return [];
    const alerts: { provider: string; message: string; severity: 'warning' | 'error' }[] = [];
    for (const p of budget.providers) {
      const pct = percentOf(p.spent_usd, p.allocated_usd);
      if (pct >= 90) {
        alerts.push({
          provider: p.provider,
          message: `${p.provider} is at ${pct.toFixed(0)}% of allocated budget`,
          severity: 'error',
        });
      } else if (pct >= 70) {
        alerts.push({
          provider: p.provider,
          message: `${p.provider} is at ${pct.toFixed(0)}% of allocated budget`,
          severity: 'warning',
        });
      }
    }
    if (spendProjection > budget.total_budget_usd) {
      alerts.push({
        provider: 'Overall',
        message: `Projected spend (${formatCurrency(spendProjection)}) exceeds total budget (${formatCurrency(budget.total_budget_usd)})`,
        severity: 'error',
      });
    }
    return alerts;
  }, [budget, spendProjection]);

  return (
    <div className="min-h-screen bg-nc-bg text-nc-text">
      {/* Tab Navigation */}
      <div className="flex items-center gap-1 border-b border-nc-border bg-nc-surface px-4 pt-3">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-nc-accent text-white'
                : 'text-nc-text-dim hover:bg-nc-surface-2 hover:text-nc-text'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-4 mt-3 p-3 rounded-lg bg-red-100 text-red-800 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2 font-bold">
            ×
          </button>
        </div>
      )}

      <div className="p-4">
        {/* ===================== DASHBOARD VIEW ===================== */}
        {activeTab === 'Dashboard' && (
          <div>
            {dashLoading && !dashboard ? (
              <div className="flex items-center justify-center py-20 text-nc-text-dim">
                <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading dashboard…
              </div>
            ) : dashboard ? (
              <>
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
                  {/* Task Counts Card */}
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-3">Task Overview</h3>
                    <div className="text-3xl font-bold text-nc-text mb-3">{dashboard.task_counts.total}</div>
                    <div className="flex flex-wrap gap-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${STATUS_BADGE.pending}`}>
                        {dashboard.task_counts.pending} Pending
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ${STATUS_BADGE.in_progress}`}>
                        {dashboard.task_counts.in_progress} In Progress
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ${STATUS_BADGE.completed}`}>
                        {dashboard.task_counts.completed} Completed
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ${STATUS_BADGE.failed}`}>
                        {dashboard.task_counts.failed} Failed
                      </span>
                    </div>
                  </div>

                  {/* Budget Card */}
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-3">Budget</h3>
                    <div className="text-3xl font-bold text-nc-text mb-1">
                      {formatCurrency(dashboard.budget.spent_usd)}
                    </div>
                    <div className="text-sm text-nc-text-dim mb-3">
                      of {formatCurrency(dashboard.budget.total_budget_usd)} total
                    </div>
                    <div className="w-full h-2 bg-nc-surface-2 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          percentOf(dashboard.budget.spent_usd, dashboard.budget.total_budget_usd) > 80
                            ? 'bg-red-500'
                            : 'bg-nc-accent'
                        }`}
                        style={{
                          width: `${percentOf(dashboard.budget.spent_usd, dashboard.budget.total_budget_usd)}%`,
                        }}
                      />
                    </div>
                    <div className="text-xs text-nc-text-dim mt-1">
                      {formatCurrency(dashboard.budget.remaining_usd)} remaining
                    </div>
                  </div>

                  {/* Activity Card */}
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-3">Recent Activity</h3>
                    <div className="text-3xl font-bold text-nc-text mb-1">
                      {dashboard.activity.recent_count}
                    </div>
                    <div className="text-sm text-nc-text-dim">
                      events recently
                    </div>
                    {dashboard.activity.last_activity_at && (
                      <div className="text-xs text-nc-text-dim mt-2">
                        Last: {formatDate(dashboard.activity.last_activity_at)}
                      </div>
                    )}
                  </div>
                </div>

                {/* Activity Feed */}
                <div className="bg-nc-surface rounded-xl border border-nc-border shadow-sm">
                  <div className="flex items-center justify-between px-5 py-4 border-b border-nc-border">
                    <h3 className="text-sm font-semibold text-nc-text">Activity Feed</h3>
                    <button
                      onClick={loadDashboard}
                      className="text-xs text-nc-accent hover:underline"
                    >
                      Refresh
                    </button>
                  </div>
                  <div className="divide-y divide-nc-border max-h-96 overflow-y-auto">
                    {activities.length === 0 ? (
                      <div className="p-5 text-center text-sm text-nc-text-dim">No recent activity</div>
                    ) : (
                      activities.map((act) => (
                        <div key={act.id} className="px-5 py-3 flex items-start gap-3">
                          <div
                            className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                              act.type === 'error'
                                ? 'bg-red-500'
                                : act.type === 'warning'
                                ? 'bg-yellow-500'
                                : act.type === 'success'
                                ? 'bg-green-500'
                                : 'bg-nc-accent'
                            }`}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-nc-text">{act.message}</p>
                            <div className="flex items-center gap-2 mt-1">
                              {act.actor && (
                                <span className="text-xs text-nc-text-dim">{act.actor}</span>
                              )}
                              <span className="text-xs text-nc-text-dim">
                                {formatDate(act.timestamp)}
                              </span>
                              {act.task_id && (
                                <span className="text-xs bg-nc-surface-2 text-nc-text-dim px-1.5 py-0.5 rounded">
                                  Task: {act.task_id.slice(0, 8)}…
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        )}

        {/* ===================== TASKS VIEW ===================== */}
        {activeTab === 'Tasks' && (
          <div>
            {/* Summary Cards */}
            {taskResponse && (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
                <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Total Tasks</h3>
                  <div className="text-3xl font-bold text-nc-text">{taskResponse.total}</div>
                </div>
                <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Current Page</h3>
                  <div className="text-3xl font-bold text-nc-text">
                    {taskResponse.page} <span className="text-sm font-normal text-nc-text-dim">of {totalPages}</span>
                  </div>
                </div>
                <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Showing</h3>
                  <div className="text-3xl font-bold text-nc-text">{taskResponse.tasks.length}</div>
                </div>
              </div>
            )}

            {/* Filters + Create */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <select
                value={taskFilters.status || ''}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-surface text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
              >
                <option value="">All Statuses</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace('_', ' ')}
                  </option>
                ))}
              </select>

              <select
                value={taskFilters.priority || ''}
                onChange={(e) => handleFilterChange('priority', e.target.value)}
                className="text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-surface text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
              >
                <option value="">All Priorities</option>
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="Filter by agent…"
                value={taskFilters.agent || ''}
                onChange={(e) => handleFilterChange('agent', e.target.value)}
                className="text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-surface text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
              />

              <input
                type="text"
                placeholder="Filter by skill…"
                value={taskFilters.skill || ''}
                onChange={(e) => handleFilterChange('skill', e.target.value)}
                className="text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-surface text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
              />

              <div className="flex-1" />

              <button
                onClick={() => setShowCreateModal(true)}
                className="bg-nc-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
              >
                + Create Task
              </button>

              <button
                onClick={loadTasks}
                className="text-sm text-nc-accent hover:underline"
              >
                Refresh
              </button>
            </div>

            {/* Tasks Table */}
            {tasksLoading && !taskResponse ? (
              <div className="flex items-center justify-center py-20 text-nc-text-dim">
                <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading tasks…
              </div>
            ) : (
              <div className="bg-nc-surface rounded-xl border border-nc-border shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-nc-surface-2 border-b border-nc-border">
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Title</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Status</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Priority</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Agent</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Skill</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Cost</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Created</th>
                        <th className="text-left px-4 py-3 font-semibold text-nc-text-dim">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-nc-border">
                      {taskResponse && taskResponse.tasks.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-4 py-10 text-center text-nc-text-dim">
                            No tasks found
                          </td>
                        </tr>
                      ) : (
                        taskResponse?.tasks.map((task) => (
                          <tr key={task.id} className="hover:bg-nc-surface-2 transition-colors">
                            <td className="px-4 py-3">
                              <div className="font-medium text-nc-text">{task.title}</div>
                              {task.description && (
                                <div className="text-xs text-nc-text-dim mt-0.5 truncate max-w-xs">
                                  {task.description}
                                </div>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`text-xs px-2 py-1 rounded-full font-medium ${
                                  STATUS_BADGE[task.status] || 'bg-nc-surface-2 text-nc-text-dim'
                                }`}
                              >
                                {task.status.replace('_', ' ')}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={`text-xs px-2 py-1 rounded-full font-medium ${
                                  PRIORITY_BADGE[task.priority] || 'bg-nc-surface-2 text-nc-text-dim'
                                }`}
                              >
                                {task.priority}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-nc-text-dim">{task.agent || '—'}</td>
                            <td className="px-4 py-3">
                              {task.skill ? (
                                <span className="text-xs bg-nc-surface-2 border border-nc-border text-nc-text px-2 py-0.5 rounded">
                                  {task.skill}
                                </span>
                              ) : (
                                <span className="text-nc-text-dim">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-nc-text-dim">
                              {task.cost_usd != null ? formatCurrency(task.cost_usd) : '—'}
                            </td>
                            <td className="px-4 py-3 text-xs text-nc-text-dim">
                              {formatDate(task.created_at)}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-1">
                                {task.status === 'pending' && (
                                  <button
                                    onClick={() => handleQuickStatus(task.id, 'in_progress')}
                                    disabled={updatingTaskId === task.id}
                                    className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded hover:bg-blue-200 transition-colors disabled:opacity-50"
                                  >
                                    ▶ Start
                                  </button>
                                )}
                                {task.status === 'in_progress' && (
                                  <>
                                    <button
                                      onClick={() => handleQuickStatus(task.id, 'completed')}
                                      disabled={updatingTaskId === task.id}
                                      className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded hover:bg-green-200 transition-colors disabled:opacity-50"
                                    >
                                      ✓ Complete
                                    </button>
                                    <button
                                      onClick={() => handleQuickStatus(task.id, 'failed')}
                                      disabled={updatingTaskId === task.id}
                                      className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded hover:bg-red-200 transition-colors disabled:opacity-50"
                                    >
                                      ✗ Fail
                                    </button>
                                  </>
                                )}
                                {(task.status === 'pending' || task.status === 'in_progress') && (
                                  <button
                                    onClick={() => handleQuickStatus(task.id, 'cancelled')}
                                    disabled={updatingTaskId === task.id}
                                    className="text-xs bg-nc-surface-2 text-nc-text-dim px-2 py-1 rounded hover:bg-nc-border transition-colors disabled:opacity-50"
                                  >
                                    Cancel
                                  </button>
                                )}
                                {(task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') && (
                                  <button
                                    onClick={() => handleQuickStatus(task.id, 'pending')}
                                    disabled={updatingTaskId === task.id}
                                    className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded hover:bg-yellow-200 transition-colors disabled:opacity-50"
                                  >
                                    ↺ Reopen
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {taskResponse && totalPages > 1 && (
                  <div className="flex items-center justify-between px-4 py-3 border-t border-nc-border">
                    <div className="text-xs text-nc-text-dim">
                      {taskResponse.total} total tasks
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        disabled={taskResponse.page <= 1}
                        onClick={() =>
                          setTaskFilters((prev) => ({ ...prev, page: (prev.page || 1) - 1 }))
                        }
                        className="text-xs px-3 py-1.5 rounded border border-nc-border bg-nc-surface text-nc-text disabled:opacity-40 hover:bg-nc-surface-2 transition-colors"
                      >
                        ← Prev
                      </button>
                      <span className="text-xs text-nc-text-dim">
                        Page {taskResponse.page} of {totalPages}
                      </span>
                      <button
                        disabled={taskResponse.page >= totalPages}
                        onClick={() =>
                          setTaskFilters((prev) => ({ ...prev, page: (prev.page || 1) + 1 }))
                        }
                        className="text-xs px-3 py-1.5 rounded border border-nc-border bg-nc-surface text-nc-text disabled:opacity-40 hover:bg-nc-surface-2 transition-colors"
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ===================== FINANCE VIEW ===================== */}
        {activeTab === 'Finance' && (
          <div>
            {financeLoading && !budget ? (
              <div className="flex items-center justify-center py-20 text-nc-text-dim">
                <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading finance data…
              </div>
            ) : budget ? (
              <>
                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Total Budget</h3>
                    <div className="text-3xl font-bold text-nc-text">
                      {formatCurrency(budget.total_budget_usd)}
                    </div>
                    <div className="text-xs text-nc-text-dim mt-1">
                      {formatCurrency(budget.total_remaining_usd)} remaining
                    </div>
                  </div>
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Total Spent</h3>
                    <div className="text-3xl font-bold text-nc-text">
                      {formatCurrency(budget.total_spent_usd)}
                    </div>
                    <div className="w-full h-2 bg-nc-surface-2 rounded-full overflow-hidden mt-2">
                      <div
                        className={`h-full rounded-full transition-all ${
                          percentOf(budget.total_spent_usd, budget.total_budget_usd) > 80
                            ? 'bg-red-500'
                            : 'bg-nc-accent'
                        }`}
                        style={{
                          width: `${percentOf(budget.total_spent_usd, budget.total_budget_usd)}%`,
                        }}
                      />
                    </div>
                    <div className="text-xs text-nc-text-dim mt-1">
                      {percentOf(budget.total_spent_usd, budget.total_budget_usd).toFixed(1)}% used
                    </div>
                  </div>
                  <div className="bg-nc-surface rounded-xl border border-nc-border p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-nc-text-dim mb-1">Spend Projection</h3>
                    <div
                      className={`text-3xl font-bold ${
                        spendProjection > budget.total_budget_usd ? 'text-red-600' : 'text-nc-text'
                      }`}
                    >
                      {formatCurrency(spendProjection)}
                    </div>
                    <div className="text-xs text-nc-text-dim mt-1">
                      Estimated end-of-month spend
                    </div>
                  </div>
                </div>

                {/* Cost Alerts */}
                {costAlerts.length > 0 && (
                  <div className="mb-6 space-y-2">
                    {costAlerts.map((alert, i) => (
                      <div
                        key={i}
                        className={`px-4 py-3 rounded-lg text-sm flex items-center gap-2 ${
                          alert.severity === 'error'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        <span>{alert.severity === 'error' ? '⚠' : '⚡'}</span>
                        <span>{alert.message}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Budget Bars Per Provider */}
                <div className="bg-nc-surface rounded-xl border border-nc-border shadow-sm">
                  <div className="flex items-center justify-between px-5 py-4 border-b border-nc-border">
                    <h3 className="text-sm font-semibold text-nc-text">Budget by Provider</h3>
                    <button
                      onClick={loadFinance}
                      className="text-xs text-nc-accent hover:underline"
                    >
                      Refresh
                    </button>
                  </div>
                  <div className="divide-y divide-nc-border">
                    {budget.providers.length === 0 ? (
                      <div className="p-5 text-center text-sm text-nc-text-dim">
                        No provider data available
                      </div>
                    ) : (
                      budget.providers.map((provider) => {
                        const pct = percentOf(provider.spent_usd, provider.allocated_usd);
                        return (
                          <div key={provider.provider} className="px-5 py-4">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-nc-text">{provider.provider}</span>
                                <span className="text-xs text-nc-text-dim">
                                  {provider.request_count} requests
                                </span>
                              </div>
                              <div className="text-sm text-nc-text">
                                <span className="font-semibold">{formatCurrency(provider.spent_usd)}</span>
                                <span className="text-nc-text-dim"> / {formatCurrency(provider.allocated_usd)}</span>
                              </div>
                            </div>
                            <div className="w-full h-3 bg-nc-surface-2 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  pct >= 90
                                    ? 'bg-red-500'
                                    : pct >= 70
                                    ? 'bg-yellow-500'
                                    : 'bg-nc-accent'
                                }`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <div className="flex items-center justify-between mt-1">
                              <span className="text-xs text-nc-text-dim">{pct.toFixed(1)}% used</span>
                              <span className="text-xs text-nc-text-dim">
                                {formatCurrency(provider.allocated_usd - provider.spent_usd)} remaining
                              </span>
                            </div>
                            {/* Mini trend sparkline */}
                            {provider.trend && provider.trend.length > 1 && (
                              <div className="mt-2 flex items-end gap-px h-8">
                                {provider.trend.map((val, idx) => {
                                  const maxVal = Math.max(...provider.trend, 1);
                                  const heightPct = (val / maxVal) * 100;
                                  return (
                                    <div
                                      key={idx}
                                      className="flex-1 bg-nc-accent/30 rounded-t hover:bg-nc-accent/60 transition-colors"
                                      style={{ height: `${Math.max(heightPct, 4)}%` }}
                                      title={
                                        provider.trend_labels?.[idx]
                                          ? `${provider.trend_labels[idx]}: ${formatCurrency(val)}`
                                          : formatCurrency(val)
                                      }
                                    />
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        )}
      </div>

      {/* ===================== CREATE TASK MODAL ===================== */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface rounded-xl border border-nc-border shadow-xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-nc-border">
              <h2 className="text-lg font-semibold text-nc-text">Create Task</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-nc-text-dim hover:text-nc-text text-xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Task title"
                  className="w-full text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">Description</label>
                <textarea
                  value={createForm.description || ''}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Task description"
                  rows={3}
                  className="w-full text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent resize-none"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Agent</label>
                  <input
                    type="text"
                    value={createForm.agent || ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, agent: e.target.value || undefined }))}
                    placeholder="Agent name"
                    className="w-full text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Skill</label>
                  <input
                    type="text"
                    value={createForm.skill || ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, skill: e.target.value || undefined }))}
                    placeholder="Linked skill"
                    className="w-full text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">Priority</label>
                <select
                  value={createForm.priority || 'medium'}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      priority: e.target.value as TaskCreateInput['priority'],
                    }))
                  }
                  className="w-full text-sm border border-nc-border rounded-lg px-3 py-2 bg-nc-bg text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                >
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-nc-border">
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-sm px-4 py-2 rounded-lg border border-nc-border bg-nc-surface text-nc-text hover:bg-nc-surface-2 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateTask}
                disabled={creating || !createForm.title.trim()}
                className="text-sm px-4 py-2 rounded-lg bg-nc-accent text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {creating ? 'Creating…' : 'Create Task'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}