'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  listApprovals,
  createApproval,
  type Approval,
  type ApprovalCreateInput,
  type ApprovalStatus,
  type ApprovalPriority,
  type AuditEntry,
  type AuditTrailResponse,
} from '../lib/approvals-api';

const API = 'http://127.0.0.1:8100/api/approvals';

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function approveApproval(id: string, notes?: string): Promise<Approval> {
  const res = await fetch(`${API}/${id}/approve`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ notes: notes || '' }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function rejectApproval(id: string, reason: string): Promise<Approval> {
  const res = await fetch(`${API}/${id}/reject`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

async function fetchAuditTrail(): Promise<AuditTrailResponse> {
  const res = await fetch(`${API}/audit`, { headers: headers() });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

type TabView = 'queue' | 'history' | 'audit';

const PRIORITY_STYLES: Record<ApprovalPriority, { bg: string; text: string; label: string }> = {
  critical: { bg: 'bg-red-100', text: 'text-red-800', label: 'Critical' },
  high: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'High' },
  medium: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Medium' },
  low: { bg: 'bg-green-100', text: 'text-green-800', label: 'Low' },
};

const STATUS_STYLES: Record<ApprovalStatus, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Pending' },
  approved: { bg: 'bg-green-100', text: 'text-green-800', label: 'Approved' },
  rejected: { bg: 'bg-red-100', text: 'text-red-800', label: 'Rejected' },
  escalated: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Escalated' },
};

const TABS: { key: TabView; label: string }[] = [
  { key: 'queue', label: 'Queue' },
  { key: 'history', label: 'History' },
  { key: 'audit', label: 'Audit' },
];

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
}

function formatRelative(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return dateStr;
  }
}

export default function ApprovalsTab() {
  const [activeTab, setActiveTab] = useState<TabView>('queue');
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [inlineNotes, setInlineNotes] = useState<Record<string, string>>({});
  const [showRejectModal, setShowRejectModal] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [approveNotesModal, setApproveNotesModal] = useState<string | null>(null);
  const [approveNotes, setApproveNotes] = useState('');

  const [createForm, setCreateForm] = useState<ApprovalCreateInput>({
    title: '',
    description: '',
    priority: 'medium',
    category: '',
    requester: '',
    assignee: '',
  });
  const [createLoading, setCreateLoading] = useState(false);

  const loadApprovals = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listApprovals();
      setApprovals(data.items || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load approvals');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAuditTrail();
      setAuditEntries(data.items || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAudit();
    } else {
      loadApprovals();
    }
  }, [activeTab, loadApprovals, loadAudit]);

  const pendingApprovals = useMemo(
    () => approvals.filter((a) => a.status === 'pending' || a.status === 'escalated'),
    [approvals]
  );

  const resolvedApprovals = useMemo(
    () => approvals.filter((a) => a.status === 'approved' || a.status === 'rejected'),
    [approvals]
  );

  const queueStats = useMemo(() => {
    const critical = pendingApprovals.filter((a) => a.priority === 'critical').length;
    const high = pendingApprovals.filter((a) => a.priority === 'high').length;
    const escalated = pendingApprovals.filter((a) => a.status === 'escalated').length;
    return { total: pendingApprovals.length, critical, high, escalated };
  }, [pendingApprovals]);

  const historyStats = useMemo(() => {
    const approved = resolvedApprovals.filter((a) => a.status === 'approved').length;
    const rejected = resolvedApprovals.filter((a) => a.status === 'rejected').length;
    return { total: resolvedApprovals.length, approved, rejected };
  }, [resolvedApprovals]);

  const auditStats = useMemo(() => {
    const actions = auditEntries.reduce<Record<string, number>>((acc, e) => {
      acc[e.action] = (acc[e.action] || 0) + 1;
      return acc;
    }, {});
    return { total: auditEntries.length, actions };
  }, [auditEntries]);

  const handleApprove = useCallback(
    async (id: string, notes?: string) => {
      try {
        setActioningId(id);
        await approveApproval(id, notes);
        setApproveNotesModal(null);
        setApproveNotes('');
        await loadApprovals();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to approve');
      } finally {
        setActioningId(null);
      }
    },
    [loadApprovals]
  );

  const handleReject = useCallback(
    async (id: string, reason: string) => {
      if (!reason.trim()) {
        setError('Rejection reason is required');
        return;
      }
      try {
        setActioningId(id);
        await rejectApproval(id, reason);
        setShowRejectModal(null);
        setRejectReason('');
        await loadApprovals();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to reject');
      } finally {
        setActioningId(null);
      }
    },
    [loadApprovals]
  );

  const handleCreate = useCallback(async () => {
    if (!createForm.title.trim() || !createForm.description.trim()) {
      setError('Title and description are required');
      return;
    }
    try {
      setCreateLoading(true);
      setError(null);
      await createApproval({
        title: createForm.title,
        description: createForm.description,
        priority: createForm.priority,
        category: createForm.category || undefined,
        requester: createForm.requester || undefined,
        assignee: createForm.assignee || undefined,
      });
      setShowCreateModal(false);
      setCreateForm({
        title: '',
        description: '',
        priority: 'medium',
        category: '',
        requester: '',
        assignee: '',
      });
      await loadApprovals();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create approval');
    } finally {
      setCreateLoading(false);
    }
  }, [createForm, loadApprovals]);

  const sortedPending = useMemo(() => {
    const priorityOrder: Record<ApprovalPriority, number> = {
      critical: 0,
      high: 1,
      medium: 2,
      low: 3,
    };
    return [...pendingApprovals].sort(
      (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]
    );
  }, [pendingApprovals]);

  const sortedResolved = useMemo(() => {
    return [...resolvedApprovals].sort(
      (a, b) => new Date(b.resolved_at || b.updated_at).getTime() - new Date(a.resolved_at || a.updated_at).getTime()
    );
  }, [resolvedApprovals]);

  const sortedAudit = useMemo(() => {
    return [...auditEntries].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [auditEntries]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-nc-text">Approvals</h2>
          <p className="text-sm text-nc-text-dim mt-1">Manage approval requests, review history, and audit trail</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-nc-accent text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
        >
          + New Approval
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-100 border border-red-200 text-red-800 rounded-lg px-4 py-3 flex items-center justify-between">
          <span className="text-sm">{error}</span>
          <button onClick={() => setError(null)} className="text-red-800 hover:text-red-900 font-bold">
            ×
          </button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex space-x-1 bg-nc-surface rounded-lg p-1 border border-nc-border">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-nc-accent text-white shadow-sm'
                : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
            }`}
          >
            {tab.label}
            {tab.key === 'queue' && queueStats.total > 0 && (
              <span className="ml-2 inline-flex items-center justify-center w-5 h-5 text-xs rounded-full bg-white/20">
                {queueStats.total}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-nc-accent border-t-transparent" />
          <span className="ml-3 text-nc-text-dim">Loading...</span>
        </div>
      )}

      {/* Queue View */}
      {!loading && activeTab === 'queue' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Total Pending</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{queueStats.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Critical</p>
              <p className="text-2xl font-bold text-red-800 mt-1">{queueStats.critical}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">High Priority</p>
              <p className="text-2xl font-bold text-yellow-800 mt-1">{queueStats.high}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Escalated</p>
              <p className="text-2xl font-bold text-blue-800 mt-1">{queueStats.escalated}</p>
            </div>
          </div>

          {/* Pending Approval Cards */}
          {sortedPending.length === 0 ? (
            <div className="text-center py-12 bg-nc-surface border border-nc-border rounded-lg">
              <p className="text-nc-text-dim text-lg">No pending approvals</p>
              <p className="text-nc-text-dim text-sm mt-1">All caught up!</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {sortedPending.map((approval) => {
                const pStyle = PRIORITY_STYLES[approval.priority];
                const sStyle = STATUS_STYLES[approval.status];
                return (
                  <div
                    key={approval.id}
                    className="bg-nc-surface border border-nc-border rounded-lg p-5 flex flex-col space-y-3 hover:shadow-md transition-shadow"
                  >
                    {/* Header row */}
                    <div className="flex items-start justify-between">
                      <h3 className="text-sm font-semibold text-nc-text leading-tight flex-1 mr-2">
                        {approval.title}
                      </h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${pStyle.bg} ${pStyle.text} whitespace-nowrap`}
                      >
                        {pStyle.label}
                      </span>
                    </div>

                    {/* Description */}
                    <p className="text-xs text-nc-text-dim line-clamp-2">{approval.description}</p>

                    {/* Meta */}
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className={`px-2 py-0.5 rounded-full ${sStyle.bg} ${sStyle.text}`}>
                        {sStyle.label}
                      </span>
                      {approval.category && (
                        <span className="px-2 py-0.5 rounded-full bg-nc-surface-2 text-nc-text-dim border border-nc-border">
                          {approval.category}
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-nc-text-dim space-y-1">
                      <div className="flex justify-between">
                        <span>Requester:</span>
                        <span className="font-medium text-nc-text">{approval.requester || 'Unknown'}</span>
                      </div>
                      {approval.assignee && (
                        <div className="flex justify-between">
                          <span>Assignee:</span>
                          <span className="font-medium text-nc-text">{approval.assignee}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span>Created:</span>
                        <span>{formatRelative(approval.created_at)}</span>
                      </div>
                    </div>

                    {/* Inline notes */}
                    <textarea
                      placeholder="Add notes (optional)..."
                      value={inlineNotes[approval.id] || ''}
                      onChange={(e) =>
                        setInlineNotes((prev) => ({ ...prev, [approval.id]: e.target.value }))
                      }
                      className="w-full text-xs border border-nc-border rounded-md p-2 bg-nc-bg text-nc-text placeholder:text-nc-text-dim resize-none focus:outline-none focus:ring-1 focus:ring-nc-accent"
                      rows={2}
                    />

                    {/* Action Buttons */}
                    <div className="flex space-x-2 pt-1">
                      <button
                        disabled={actioningId === approval.id}
                        onClick={() => {
                          const notes = inlineNotes[approval.id];
                          if (notes && notes.trim()) {
                            handleApprove(approval.id, notes);
                          } else {
                            setApproveNotesModal(approval.id);
                          }
                        }}
                        className="flex-1 px-3 py-1.5 bg-green-100 text-green-800 rounded-md text-xs font-medium hover:bg-green-200 transition-colors disabled:opacity-50"
                      >
                        {actioningId === approval.id ? '...' : '✓ Approve'}
                      </button>
                      <button
                        disabled={actioningId === approval.id}
                        onClick={() => {
                          const notes = inlineNotes[approval.id];
                          if (notes && notes.trim()) {
                            handleReject(approval.id, notes);
                          } else {
                            setShowRejectModal(approval.id);
                          }
                        }}
                        className="flex-1 px-3 py-1.5 bg-red-100 text-red-800 rounded-md text-xs font-medium hover:bg-red-200 transition-colors disabled:opacity-50"
                      >
                        {actioningId === approval.id ? '...' : '✗ Reject'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* History View */}
      {!loading && activeTab === 'history' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Total Resolved</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{historyStats.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Approved</p>
              <p className="text-2xl font-bold text-green-800 mt-1">{historyStats.approved}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Rejected</p>
              <p className="text-2xl font-bold text-red-800 mt-1">{historyStats.rejected}</p>
            </div>
          </div>

          {/* Resolved Approval Cards */}
          {sortedResolved.length === 0 ? (
            <div className="text-center py-12 bg-nc-surface border border-nc-border rounded-lg">
              <p className="text-nc-text-dim text-lg">No resolved approvals yet</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {sortedResolved.map((approval) => {
                const pStyle = PRIORITY_STYLES[approval.priority];
                const sStyle = STATUS_STYLES[approval.status];
                return (
                  <div
                    key={approval.id}
                    className="bg-nc-surface border border-nc-border rounded-lg p-5 flex flex-col space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <h3 className="text-sm font-semibold text-nc-text leading-tight flex-1 mr-2">
                        {approval.title}
                      </h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${sStyle.bg} ${sStyle.text} whitespace-nowrap`}
                      >
                        {sStyle.label}
                      </span>
                    </div>

                    <p className="text-xs text-nc-text-dim line-clamp-2">{approval.description}</p>

                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className={`px-2 py-0.5 rounded-full ${pStyle.bg} ${pStyle.text}`}>
                        {pStyle.label}
                      </span>
                      {approval.category && (
                        <span className="px-2 py-0.5 rounded-full bg-nc-surface-2 text-nc-text-dim border border-nc-border">
                          {approval.category}
                        </span>
                      )}
                    </div>

                    <div className="text-xs text-nc-text-dim space-y-1">
                      <div className="flex justify-between">
                        <span>Requester:</span>
                        <span className="font-medium text-nc-text">{approval.requester || 'Unknown'}</span>
                      </div>
                      {approval.assignee && (
                        <div className="flex justify-between">
                          <span>Resolved by:</span>
                          <span className="font-medium text-nc-text">{approval.assignee}</span>
                        </div>
                      )}
                      {approval.resolved_at && (
                        <div className="flex justify-between">
                          <span>Resolved:</span>
                          <span>{formatDate(approval.resolved_at)}</span>
                        </div>
                      )}
                    </div>

                    {/* Notes / Reason */}
                    {(approval.notes || approval.reason) && (
                      <div className="bg-nc-surface-2 border border-nc-border rounded-md p-2">
                        <p className="text-xs text-nc-text-dim font-medium mb-1">
                          {approval.status === 'rejected' ? 'Rejection Reason' : 'Notes'}
                        </p>
                        <p className="text-xs text-nc-text">
                          {approval.status === 'rejected' ? approval.reason : approval.notes}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Audit View */}
      {!loading && activeTab === 'audit' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Total Entries</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{auditStats.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Unique Actions</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{Object.keys(auditStats.actions).length}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-lg p-4">
              <p className="text-sm text-nc-text-dim">Action Breakdown</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(auditStats.actions).map(([action, count]) => (
                  <span
                    key={action}
                    className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-xs font-medium"
                  >
                    {action}: {count}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Audit Trail */}
          {sortedAudit.length === 0 ? (
            <div className="text-center py-12 bg-nc-surface border border-nc-border rounded-lg">
              <p className="text-nc-text-dim text-lg">No audit entries yet</p>
            </div>
          ) : (
            <div className="bg-nc-surface border border-nc-border rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-nc-surface-2 border-b border-nc-border">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-nc-text-dim uppercase tracking-wider">
                        Timestamp
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-nc-text-dim uppercase tracking-wider">
                        Action
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-nc-text-dim uppercase tracking-wider">
                        Actor
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-nc-text-dim uppercase tracking-wider">
                        Approval ID
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-nc-text-dim uppercase tracking-wider">
                        Details
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-nc-border">
                    {sortedAudit.map((entry) => {
                      const actionColor =
                        entry.action === 'approved'
                          ? 'bg-green-100 text-green-800'
                          : entry.action === 'rejected'
                          ? 'bg-red-100 text-red-800'
                          : entry.action === 'escalated'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-blue-100 text-blue-800';
                      return (
                        <tr key={entry.id} className="hover:bg-nc-surface-2 transition-colors">
                          <td className="px-4 py-3 text-xs text-nc-text-dim whitespace-nowrap">
                            {formatDate(entry.timestamp)}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${actionColor}`}>
                              {entry.action}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-nc-text font-medium">{entry.actor}</td>
                          <td className="px-4 py-3 text-xs text-nc-text-dim font-mono">
                            {entry.approval_id.slice(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-xs text-nc-text-dim max-w-xs truncate">
                            {Object.keys(entry.details).length > 0
                              ? JSON.stringify(entry.details)
                              : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Approval Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface border border-nc-border rounded-xl shadow-xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-nc-border">
              <h3 className="text-lg font-semibold text-nc-text">Create Approval Request</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-nc-text-dim hover:text-nc-text text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-nc-text-dim mb-1">
                  Title <span className="text-red-800">*</span>
                </label>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
                  className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
                  placeholder="Approval request title"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-nc-text-dim mb-1">
                  Description <span className="text-red-800">*</span>
                </label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent resize-none"
                  rows={3}
                  placeholder="Describe what needs approval"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-nc-text-dim mb-1">Priority</label>
                  <select
                    value={createForm.priority}
                    onChange={(e) =>
                      setCreateForm((f) => ({ ...f, priority: e.target.value as ApprovalPriority }))
                    }
                    className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-nc-text-dim mb-1">Category</label>
                  <input
                    type="text"
                    value={createForm.category}
                    onChange={(e) => setCreateForm((f) => ({ ...f, category: e.target.value }))}
                    className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
                    placeholder="e.g., deployment"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-nc-text-dim mb-1">Requester</label>
                  <input
                    type="text"
                    value={createForm.requester}
                    onChange={(e) => setCreateForm((f) => ({ ...f, requester: e.target.value }))}
                    className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
                    placeholder="Who is requesting"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-nc-text-dim mb-1">Assignee</label>
                  <input
                    type="text"
                    value={createForm.assignee}
                    onChange={(e) => setCreateForm((f) => ({ ...f, assignee: e.target.value }))}
                    className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent"
                    placeholder="Who should approve"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-3 px-6 py-4 border-t border-nc-border">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-sm font-medium text-nc-text-dim hover:text-nc-text border border-nc-border rounded-md hover:bg-nc-surface-2 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createLoading}
                className="px-4 py-2 text-sm font-medium bg-nc-accent text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {createLoading ? 'Creating...' : 'Create Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Approve with Notes Modal */}
      {approveNotesModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface border border-nc-border rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-nc-border">
              <h3 className="text-lg font-semibold text-nc-text">Approve Request</h3>
              <button
                onClick={() => {
                  setApproveNotesModal(null);
                  setApproveNotes('');
                }}
                className="text-nc-text-dim hover:text-nc-text text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <p className="text-sm text-nc-text-dim">Add optional notes for this approval:</p>
              <textarea
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent resize-none"
                rows={3}
                placeholder="Approval notes (optional)"
              />
            </div>

            <div className="flex justify-end space-x-3 px-6 py-4 border-t border-nc-border">
              <button
                onClick={() => {
                  setApproveNotesModal(null);
                  setApproveNotes('');
                }}
                className="px-4 py-2 text-sm font-medium text-nc-text-dim hover:text-nc-text border border-nc-border rounded-md hover:bg-nc-surface-2 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleApprove(approveNotesModal, approveNotes)}
                disabled={actioningId === approveNotesModal}
                className="px-4 py-2 text-sm font-medium bg-green-100 text-green-800 rounded-md hover:bg-green-200 transition-colors disabled:opacity-50"
              >
                {actioningId === approveNotesModal ? 'Approving...' : '✓ Approve'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject with Reason Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface border border-nc-border rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-nc-border">
              <h3 className="text-lg font-semibold text-nc-text">Reject Request</h3>
              <button
                onClick={() => {
                  setShowRejectModal(null);
                  setRejectReason('');
                }}
                className="text-nc-text-dim hover:text-nc-text text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <p className="text-sm text-nc-text-dim">Please provide a reason for rejection:</p>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                className="w-full border border-nc-border rounded-md px-3 py-2 text-sm bg-nc-bg text-nc-text focus:outline-none focus:ring-1 focus:ring-nc-accent resize-none"
                rows={3}
                placeholder="Rejection reason (required)"
              />
            </div>

            <div className="flex justify-end space-x-3 px-6 py-4 border-t border-nc-border">
              <button
                onClick={() => {
                  setShowRejectModal(null);
                  setRejectReason('');
                }}
                className="px-4 py-2 text-sm font-medium text-nc-text-dim hover:text-nc-text border border-nc-border rounded-md hover:bg-nc-surface-2 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleReject(showRejectModal, rejectReason)}
                disabled={actioningId === showRejectModal || !rejectReason.trim()}
                className="px-4 py-2 text-sm font-medium bg-red-100 text-red-800 rounded-md hover:bg-red-200 transition-colors disabled:opacity-50"
              >
                {actioningId === showRejectModal ? 'Rejecting...' : '✗ Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}