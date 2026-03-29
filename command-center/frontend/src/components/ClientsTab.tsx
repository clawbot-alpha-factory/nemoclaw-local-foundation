'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type {
  Client,
  ClientInput,
  ClientListFilters,
  ClientListResponse,
  Deliverable,
  DeliverableInput,
  ClientHealthScore,
  Project,
} from '../lib/clients-api';

const API = 'http://127.0.0.1:8100/api/clients';

function headers(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cc-token') : null;
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

async function fetchClients(filters?: ClientListFilters): Promise<ClientListResponse> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.tier) params.set('tier', filters.tier);
  if (filters?.search) params.set('search', filters.search);
  if (filters?.page) params.set('page', String(filters.page));
  if (filters?.limit) params.set('limit', String(filters.limit));
  if (filters?.sort_by) params.set('sort_by', filters.sort_by);
  if (filters?.sort_order) params.set('sort_order', filters.sort_order);
  const qs = params.toString();
  const res = await fetch(`${API}${qs ? `?${qs}` : ''}`, { headers: headers() });
  return handleResponse<ClientListResponse>(res);
}

async function createClient(input: ClientInput): Promise<Client> {
  const res = await fetch(API, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(input),
  });
  return handleResponse<Client>(res);
}

async function fetchDeliverables(clientId?: string): Promise<Deliverable[]> {
  const url = clientId ? `${API}/${clientId}/deliverables` : `${API}/deliverables`;
  const res = await fetch(url, { headers: headers() });
  return handleResponse<Deliverable[]>(res);
}

async function updateDeliverableStatus(
  clientId: string,
  deliverableId: string,
  status: Deliverable['status']
): Promise<Deliverable> {
  const res = await fetch(`${API}/${clientId}/deliverables/${deliverableId}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ status }),
  });
  return handleResponse<Deliverable>(res);
}

async function fetchHealthScores(): Promise<ClientHealthScore[]> {
  const res = await fetch(`${API}/health`, { headers: headers() });
  return handleResponse<ClientHealthScore[]>(res);
}

const STATUS_BADGE: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-red-100 text-red-800',
  prospect: 'bg-blue-100 text-blue-800',
  archived: 'bg-yellow-100 text-yellow-800',
};

const DELIVERABLE_STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
};

const RISK_BADGE: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-red-100 text-red-800',
  critical: 'bg-red-100 text-red-800',
};

const TIER_BADGE: Record<string, string> = {
  enterprise: 'bg-blue-100 text-blue-800',
  professional: 'bg-green-100 text-green-800',
  starter: 'bg-yellow-100 text-yellow-800',
};

type TabView = 'clients' | 'deliverables' | 'health';

const DELIVERABLE_STATUSES: Deliverable['status'][] = [
  'pending',
  'in_progress',
  'completed',
  'approved',
  'rejected',
];

export default function ClientsTab() {
  const [activeTab, setActiveTab] = useState<TabView>('clients');
  const [clients, setClients] = useState<Client[]>([]);
  const [totalClients, setTotalClients] = useState(0);
  const [deliverables, setDeliverables] = useState<Deliverable[]>([]);
  const [healthScores, setHealthScores] = useState<ClientHealthScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [tierFilter, setTierFilter] = useState<string>('');

  const [newClient, setNewClient] = useState<ClientInput>({
    name: '',
    email: '',
    phone: '',
    company: '',
    industry: '',
    status: 'prospect',
    tier: 'starter',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    website: '',
    address: '',
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const loadClients = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const filters: ClientListFilters = {
        limit: 100,
      };
      if (searchQuery) filters.search = searchQuery;
      if (statusFilter) filters.status = statusFilter;
      if (tierFilter) filters.tier = tierFilter;
      const resp = await fetchClients(filters);
      setClients(resp.items || []);
      setTotalClients(resp.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load clients');
      setClients([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, statusFilter, tierFilter]);

  const loadDeliverables = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchDeliverables();
      setDeliverables(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || 'Failed to load deliverables');
      setDeliverables([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchHealthScores();
      setHealthScores(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || 'Failed to load health scores');
      setHealthScores([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'clients') loadClients();
    else if (activeTab === 'deliverables') loadDeliverables();
    else if (activeTab === 'health') loadHealth();
  }, [activeTab, loadClients, loadDeliverables, loadHealth]);

  const handleAddClient = useCallback(async () => {
    if (!newClient.name.trim()) return;
    try {
      setSubmitting(true);
      await createClient(newClient);
      setShowAddModal(false);
      setNewClient({
        name: '',
        email: '',
        phone: '',
        company: '',
        industry: '',
        status: 'prospect',
        tier: 'starter',
        contact_name: '',
        contact_email: '',
        contact_phone: '',
        website: '',
        address: '',
        notes: '',
      });
      loadClients();
    } catch (err: any) {
      setError(err.message || 'Failed to create client');
    } finally {
      setSubmitting(false);
    }
  }, [newClient, loadClients]);

  const handleQuickStatusUpdate = useCallback(
    async (clientId: string, deliverableId: string, newStatus: Deliverable['status']) => {
      try {
        await updateDeliverableStatus(clientId, deliverableId, newStatus);
        setDeliverables((prev) =>
          prev.map((d) => (d.id === deliverableId ? { ...d, status: newStatus } : d))
        );
      } catch (err: any) {
        setError(err.message || 'Failed to update deliverable');
      }
    },
    []
  );

  const clientSummary = useMemo(() => {
    const active = clients.filter((c) => c.status === 'active').length;
    const prospect = clients.filter((c) => c.status === 'prospect').length;
    const inactive = clients.filter((c) => c.status === 'inactive').length;
    return { total: clients.length, active, prospect, inactive };
  }, [clients]);

  const deliverableSummary = useMemo(() => {
    const pending = deliverables.filter((d) => d.status === 'pending').length;
    const inProgress = deliverables.filter((d) => d.status === 'in_progress').length;
    const completed = deliverables.filter((d) => d.status === 'completed').length;
    const overdue = deliverables.filter(
      (d) => d.due_date && new Date(d.due_date) < new Date() && d.status !== 'completed' && d.status !== 'approved'
    ).length;
    return { total: deliverables.length, pending, inProgress, completed, overdue };
  }, [deliverables]);

  const healthSummary = useMemo(() => {
    const avgScore =
      healthScores.length > 0
        ? Math.round(healthScores.reduce((s, h) => s + h.overall_score, 0) / healthScores.length)
        : 0;
    const critical = healthScores.filter((h) => h.risk_level === 'critical').length;
    const high = healthScores.filter((h) => h.risk_level === 'high').length;
    const low = healthScores.filter((h) => h.risk_level === 'low').length;
    return { total: healthScores.length, avgScore, critical, high, low };
  }, [healthScores]);

  const clientMap = useMemo(() => {
    const map: Record<string, string> = {};
    clients.forEach((c) => {
      map[c.id] = c.name;
    });
    return map;
  }, [clients]);

  const getHealthColor = (score: number) => {
    if (score >= 80) return 'text-green-800';
    if (score >= 60) return 'text-yellow-800';
    if (score >= 40) return 'text-red-800';
    return 'text-red-800';
  };

  const getHealthBarColor = (score: number) => {
    if (score >= 80) return 'bg-green-100';
    if (score >= 60) return 'bg-yellow-100';
    if (score >= 40) return 'bg-red-100';
    return 'bg-red-100';
  };

  const getHealthBarFill = (score: number) => {
    if (score >= 80) return 'bg-green-800';
    if (score >= 60) return 'bg-yellow-800';
    if (score >= 40) return 'bg-red-800';
    return 'bg-red-800';
  };

  const formatDate = (d?: string) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const isOverdue = (dueDate?: string, status?: string) => {
    if (!dueDate) return false;
    if (status === 'completed' || status === 'approved') return false;
    return new Date(dueDate) < new Date();
  };

  const tabs: { key: TabView; label: string }[] = [
    { key: 'clients', label: 'Clients' },
    { key: 'deliverables', label: 'Deliverables' },
    { key: 'health', label: 'Health' },
  ];

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-nc-border pb-0">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab.key
                ? 'bg-nc-accent text-white'
                : 'text-nc-text-dim hover:text-nc-text hover:bg-nc-surface-2'
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        {activeTab === 'clients' && (
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 text-sm font-medium bg-nc-accent text-white rounded-lg hover:opacity-90 transition-opacity"
          >
            + Add Client
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-100 text-red-800 px-4 py-3 rounded-lg text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">
            ×
          </button>
        </div>
      )}

      {/* ============ CLIENTS VIEW ============ */}
      {activeTab === 'clients' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Total Clients</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{clientSummary.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Active</p>
              <p className="text-2xl font-bold text-green-800 mt-1">{clientSummary.active}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Prospects</p>
              <p className="text-2xl font-bold text-blue-800 mt-1">{clientSummary.prospect}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Inactive</p>
              <p className="text-2xl font-bold text-red-800 mt-1">{clientSummary.inactive}</p>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <input
              type="text"
              placeholder="Search clients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
            >
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="prospect">Prospect</option>
              <option value="archived">Archived</option>
            </select>
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-surface text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
            >
              <option value="">All Tiers</option>
              <option value="enterprise">Enterprise</option>
              <option value="professional">Professional</option>
              <option value="starter">Starter</option>
            </select>
          </div>

          {/* Client Cards Grid */}
          {loading ? (
            <div className="text-center py-12 text-nc-text-dim">Loading clients…</div>
          ) : clients.length === 0 ? (
            <div className="text-center py-12 text-nc-text-dim">
              No clients found.{' '}
              <button onClick={() => setShowAddModal(true)} className="text-nc-accent underline">
                Add one
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {clients.map((client) => (
                <div
                  key={client.id}
                  className="bg-nc-surface border border-nc-border rounded-xl p-5 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="text-nc-text font-semibold text-base truncate">{client.name}</h3>
                      {client.company && (
                        <p className="text-nc-text-dim text-sm truncate">{client.company}</p>
                      )}
                    </div>
                    {/* Health indicator dot */}
                    <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                      <span
                        className={`inline-block w-3 h-3 rounded-full ${
                          client.status === 'active'
                            ? 'bg-green-800'
                            : client.status === 'prospect'
                            ? 'bg-blue-800'
                            : client.status === 'inactive'
                            ? 'bg-red-800'
                            : 'bg-yellow-800'
                        }`}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 mb-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_BADGE[client.status] || 'bg-nc-surface-2 text-nc-text-dim'
                      }`}
                    >
                      {client.status}
                    </span>
                    {client.tier && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          TIER_BADGE[client.tier] || 'bg-nc-surface-2 text-nc-text-dim'
                        }`}
                      >
                        {client.tier}
                      </span>
                    )}
                    {client.industry && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-nc-surface-2 text-nc-text-dim">
                        {client.industry}
                      </span>
                    )}
                  </div>

                  <div className="space-y-1 text-sm text-nc-text-dim">
                    {client.contact_name && (
                      <p className="truncate">
                        <span className="font-medium text-nc-text">Contact:</span> {client.contact_name}
                      </p>
                    )}
                    {(client.email || client.contact_email) && (
                      <p className="truncate">
                        <span className="font-medium text-nc-text">Email:</span>{' '}
                        {client.contact_email || client.email}
                      </p>
                    )}
                    {client.website && (
                      <p className="truncate">
                        <span className="font-medium text-nc-text">Web:</span> {client.website}
                      </p>
                    )}
                  </div>

                  <div className="mt-3 pt-3 border-t border-nc-border flex items-center justify-between text-xs text-nc-text-dim">
                    <span>Created {formatDate(client.created_at)}</span>
                    <span>Updated {formatDate(client.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ============ DELIVERABLES VIEW ============ */}
      {activeTab === 'deliverables' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Total Deliverables</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{deliverableSummary.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Pending</p>
              <p className="text-2xl font-bold text-yellow-800 mt-1">{deliverableSummary.pending}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">In Progress</p>
              <p className="text-2xl font-bold text-blue-800 mt-1">{deliverableSummary.inProgress}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Overdue</p>
              <p className="text-2xl font-bold text-red-800 mt-1">{deliverableSummary.overdue}</p>
            </div>
          </div>

          {/* Deliverables Table */}
          {loading ? (
            <div className="text-center py-12 text-nc-text-dim">Loading deliverables…</div>
          ) : deliverables.length === 0 ? (
            <div className="text-center py-12 text-nc-text-dim">No deliverables found.</div>
          ) : (
            <div className="bg-nc-surface border border-nc-border rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-nc-surface-2 border-b border-nc-border">
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Name</th>
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Client</th>
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Status</th>
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Due Date</th>
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Type</th>
                      <th className="text-left px-4 py-3 font-semibold text-nc-text">Quick Update</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deliverables.map((deliverable) => (
                      <tr
                        key={deliverable.id}
                        className="border-b border-nc-border hover:bg-nc-surface-2 transition-colors"
                      >
                        <td className="px-4 py-3 text-nc-text font-medium">
                          <div className="max-w-xs truncate">{deliverable.name}</div>
                          {deliverable.description && (
                            <div className="text-xs text-nc-text-dim truncate max-w-xs mt-0.5">
                              {deliverable.description}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-nc-text-dim">
                          {clientMap[deliverable.client_id] || deliverable.client_id?.slice(0, 8) || '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              DELIVERABLE_STATUS_BADGE[deliverable.status] ||
                              'bg-nc-surface-2 text-nc-text-dim'
                            }`}
                          >
                            {deliverable.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`text-sm ${
                              isOverdue(deliverable.due_date, deliverable.status)
                                ? 'text-red-800 font-semibold'
                                : 'text-nc-text-dim'
                            }`}
                          >
                            {formatDate(deliverable.due_date)}
                            {isOverdue(deliverable.due_date, deliverable.status) && (
                              <span className="ml-1 text-xs bg-red-100 text-red-800 px-1.5 py-0.5 rounded-full">
                                OVERDUE
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-nc-text-dim">{deliverable.type || '—'}</td>
                        <td className="px-4 py-3">
                          <select
                            value={deliverable.status}
                            onChange={(e) =>
                              handleQuickStatusUpdate(
                                deliverable.client_id,
                                deliverable.id,
                                e.target.value as Deliverable['status']
                              )
                            }
                            className="px-2 py-1 text-xs border border-nc-border rounded-lg bg-nc-surface text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                          >
                            {DELIVERABLE_STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {s.replace('_', ' ')}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ HEALTH VIEW ============ */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Monitored Clients</p>
              <p className="text-2xl font-bold text-nc-text mt-1">{healthSummary.total}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Avg Health Score</p>
              <p className={`text-2xl font-bold mt-1 ${getHealthColor(healthSummary.avgScore)}`}>
                {healthSummary.avgScore}%
              </p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Critical Risk</p>
              <p className="text-2xl font-bold text-red-800 mt-1">{healthSummary.critical}</p>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <p className="text-nc-text-dim text-xs uppercase tracking-wide">Low Risk</p>
              <p className="text-2xl font-bold text-green-800 mt-1">{healthSummary.low}</p>
            </div>
          </div>

          {/* Health Scores */}
          {loading ? (
            <div className="text-center py-12 text-nc-text-dim">Loading health scores…</div>
          ) : healthScores.length === 0 ? (
            <div className="text-center py-12 text-nc-text-dim">No health data available.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {healthScores
                .sort((a, b) => a.overall_score - b.overall_score)
                .map((health) => (
                  <div
                    key={health.client_id}
                    className="bg-nc-surface border border-nc-border rounded-xl p-5"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-nc-text font-semibold text-base">
                          {health.client_name}
                        </h3>
                        <span
                          className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                            RISK_BADGE[health.risk_level] || 'bg-nc-surface-2 text-nc-text-dim'
                          }`}
                        >
                          {health.risk_level} risk
                        </span>
                      </div>
                      <div className={`text-3xl font-bold ${getHealthColor(health.overall_score)}`}>
                        {health.overall_score}
                      </div>
                    </div>

                    {/* Overall Score Bar */}
                    <div className="mb-4">
                      <div className="flex items-center justify-between text-xs text-nc-text-dim mb-1">
                        <span>Overall Score</span>
                        <span>{health.overall_score}%</span>
                      </div>
                      <div className={`w-full h-2 rounded-full ${getHealthBarColor(health.overall_score)}`}>
                        <div
                          className={`h-2 rounded-full transition-all ${getHealthBarFill(health.overall_score)}`}
                          style={{ width: `${health.overall_score}%` }}
                        />
                      </div>
                    </div>

                    {/* Contributing Factors */}
                    <div className="space-y-2">
                      {health.engagement_score !== undefined && (
                        <div>
                          <div className="flex items-center justify-between text-xs text-nc-text-dim mb-0.5">
                            <span>Engagement</span>
                            <span>{health.engagement_score}%</span>
                          </div>
                          <div className={`w-full h-1.5 rounded-full ${getHealthBarColor(health.engagement_score)}`}>
                            <div
                              className={`h-1.5 rounded-full ${getHealthBarFill(health.engagement_score)}`}
                              style={{ width: `${health.engagement_score}%` }}
                            />
                          </div>
                        </div>
                      )}
                      {health.delivery_score !== undefined && (
                        <div>
                          <div className="flex items-center justify-between text-xs text-nc-text-dim mb-0.5">
                            <span>Delivery</span>
                            <span>{health.delivery_score}%</span>
                          </div>
                          <div className={`w-full h-1.5 rounded-full ${getHealthBarColor(health.delivery_score)}`}>
                            <div
                              className={`h-1.5 rounded-full ${getHealthBarFill(health.delivery_score)}`}
                              style={{ width: `${health.delivery_score}%` }}
                            />
                          </div>
                        </div>
                      )}
                      {health.satisfaction_score !== undefined && (
                        <div>
                          <div className="flex items-center justify-between text-xs text-nc-text-dim mb-0.5">
                            <span>Satisfaction</span>
                            <span>{health.satisfaction_score}%</span>
                          </div>
                          <div className={`w-full h-1.5 rounded-full ${getHealthBarColor(health.satisfaction_score)}`}>
                            <div
                              className={`h-1.5 rounded-full ${getHealthBarFill(health.satisfaction_score)}`}
                              style={{ width: `${health.satisfaction_score}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Meta Info */}
                    <div className="mt-4 pt-3 border-t border-nc-border grid grid-cols-2 gap-2 text-xs text-nc-text-dim">
                      {health.open_projects !== undefined && (
                        <div>
                          <span className="font-medium text-nc-text">{health.open_projects}</span> open
                          projects
                        </div>
                      )}
                      {health.overdue_deliverables !== undefined && (
                        <div>
                          <span
                            className={`font-medium ${
                              health.overdue_deliverables > 0 ? 'text-red-800' : 'text-nc-text'
                            }`}
                          >
                            {health.overdue_deliverables}
                          </span>{' '}
                          overdue
                        </div>
                      )}
                      {health.last_activity && (
                        <div className="col-span-2">
                          Last activity: {formatDate(health.last_activity)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* ============ ADD CLIENT MODAL ============ */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface border border-nc-border rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-nc-border">
              <h2 className="text-lg font-bold text-nc-text">Add New Client</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-nc-text-dim hover:text-nc-text text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">
                  Client Name <span className="text-red-800">*</span>
                </label>
                <input
                  type="text"
                  value={newClient.name}
                  onChange={(e) => setNewClient((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Enter client name"
                  className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                />
              </div>

              {/* Company & Industry */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Company</label>
                  <input
                    type="text"
                    value={newClient.company || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, company: e.target.value }))}
                    placeholder="Company name"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Industry</label>
                  <input
                    type="text"
                    value={newClient.industry || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, industry: e.target.value }))}
                    placeholder="e.g. Technology"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
              </div>

              {/* Status & Tier */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Status</label>
                  <select
                    value={newClient.status || 'prospect'}
                    onChange={(e) =>
                      setNewClient((p) => ({
                        ...p,
                        status: e.target.value as ClientInput['status'],
                      }))
                    }
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="prospect">Prospect</option>
                    <option value="archived">Archived</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Tier</label>
                  <select
                    value={newClient.tier || 'starter'}
                    onChange={(e) =>
                      setNewClient((p) => ({
                        ...p,
                        tier: e.target.value as ClientInput['tier'],
                      }))
                    }
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  >
                    <option value="enterprise">Enterprise</option>
                    <option value="professional">Professional</option>
                    <option value="starter">Starter</option>
                  </select>
                </div>
              </div>

              {/* Email & Phone */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Email</label>
                  <input
                    type="email"
                    value={newClient.email || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, email: e.target.value }))}
                    placeholder="email@example.com"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Phone</label>
                  <input
                    type="tel"
                    value={newClient.phone || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, phone: e.target.value }))}
                    placeholder="+1 (555) 000-0000"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
              </div>

              {/* Contact Name & Contact Email */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Contact Name</label>
                  <input
                    type="text"
                    value={newClient.contact_name || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, contact_name: e.target.value }))}
                    placeholder="Primary contact"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Contact Email</label>
                  <input
                    type="email"
                    value={newClient.contact_email || ''}
                    onChange={(e) => setNewClient((p) => ({ ...p, contact_email: e.target.value }))}
                    placeholder="contact@example.com"
                    className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>
              </div>

              {/* Website */}
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">Website</label>
                <input
                  type="url"
                  value={newClient.website || ''}
                  onChange={(e) => setNewClient((p) => ({ ...p, website: e.target.value }))}
                  placeholder="https://example.com"
                  className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                />
              </div>

              {/* Address */}
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">Address</label>
                <input
                  type="text"
                  value={newClient.address || ''}
                  onChange={(e) => setNewClient((p) => ({ ...p, address: e.target.value }))}
                  placeholder="123 Main St, City, State"
                  className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-nc-text mb-1">Notes</label>
                <textarea
                  value={newClient.notes || ''}
                  onChange={(e) => setNewClient((p) => ({ ...p, notes: e.target.value }))}
                  placeholder="Additional notes..."
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-nc-border rounded-lg bg-nc-bg text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 p-6 border-t border-nc-border">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-sm font-medium text-nc-text-dim bg-nc-surface-2 border border-nc-border rounded-lg hover:bg-nc-surface transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddClient}
                disabled={submitting || !newClient.name.trim()}
                className="px-4 py-2 text-sm font-medium bg-nc-accent text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Creating…' : 'Create Client'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}