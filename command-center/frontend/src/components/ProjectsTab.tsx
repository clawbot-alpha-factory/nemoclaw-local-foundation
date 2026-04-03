'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  listProjects,
  createProject,
  updateProject,
  deleteProject,
  listTemplates,
  getProject,
  addMilestone,
  updateMilestone,
  deleteMilestone,
  fetchDeliverables,
  fetchProjectTeam,
} from '../lib/projects-api';
import type {
  Project,
  ProjectInput,
  ProjectTemplate,
  Milestone,
  MilestoneInput,
  ProjectListFilters,
  Deliverable,
  TeamMember,
} from '../lib/projects-api';

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  planning: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Planning' },
  active: { bg: 'bg-green-100', text: 'text-green-800', label: 'Active' },
  paused: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Paused' },
  completed: { bg: 'bg-green-100', text: 'text-green-800', label: 'Completed' },
  archived: { bg: 'bg-red-100', text: 'text-red-800', label: 'Archived' },
};

const PRIORITY_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  critical: { bg: 'bg-red-100', text: 'text-red-800', label: 'Critical' },
  high: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'High' },
  medium: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Medium' },
  low: { bg: 'bg-green-100', text: 'text-green-800', label: 'Low' },
};

const MILESTONE_STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Pending' },
  in_progress: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'In Progress' },
  completed: { bg: 'bg-green-100', text: 'text-green-800', label: 'Completed' },
  overdue: { bg: 'bg-red-100', text: 'text-red-800', label: 'Overdue' },
};

type TabView = 'projects' | 'templates' | 'timeline';

function Badge({ bg, text, label }: { bg: string; text: string; label: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${bg} ${text}`}>
      {label}
    </span>
  );
}

function ProgressBar({ milestones }: { milestones?: Milestone[] }) {
  if (!milestones || milestones.length === 0) {
    return (
      <div className="w-full bg-nc-surface-2 rounded-full h-2">
        <div className="bg-nc-border rounded-full h-2" style={{ width: '0%' }} />
      </div>
    );
  }
  const completed = milestones.filter((m) => m.status === 'completed').length;
  const pct = Math.round((completed / milestones.length) * 100);
  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-nc-text-dim mb-1">
        <span>{completed}/{milestones.length} milestones</span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-nc-surface-2 rounded-full h-2">
        <div className="bg-nc-accent rounded-full h-2 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AgentAvatars({ owner }: { owner?: string }) {
  if (!owner) return null;
  const initials = owner
    .split(/[\s_-]+/)
    .map((w) => w[0]?.toUpperCase())
    .join('')
    .slice(0, 2);
  return (
    <div className="flex -space-x-1">
      <div className="w-7 h-7 rounded-full bg-nc-accent text-white flex items-center justify-center text-xs font-semibold border-2 border-nc-surface">
        {initials}
      </div>
    </div>
  );
}

export default function ProjectsTab() {
  const [activeTab, setActiveTab] = useState<TabView>('projects');
  const [projects, setProjects] = useState<Project[]>([]);
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalProjects, setTotalProjects] = useState(0);

  // filters
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFromTemplate, setCreateFromTemplate] = useState<ProjectTemplate | null>(null);
  const [createForm, setCreateForm] = useState<ProjectInput>({
    name: '',
    description: '',
    status: 'planning',
    priority: 'medium',
    owner: '',
    tags: [],
  });
  const [createLoading, setCreateLoading] = useState(false);

  // milestone inline editing
  const [editingMilestone, setEditingMilestone] = useState<{
    projectId: string;
    milestone: Milestone;
  } | null>(null);
  const [milestoneForm, setMilestoneForm] = useState<MilestoneInput>({
    title: '',
    description: '',
    due_date: '',
    status: 'pending',
  });

  // add milestone
  const [addingMilestoneProjectId, setAddingMilestoneProjectId] = useState<string | null>(null);
  const [newMilestoneForm, setNewMilestoneForm] = useState<MilestoneInput>({
    title: '',
    description: '',
    due_date: '',
    status: 'pending',
  });

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const filters: ProjectListFilters = {};
      if (statusFilter) filters.status = statusFilter;
      if (priorityFilter) filters.priority = priorityFilter;
      if (searchQuery) filters.search = searchQuery;
      filters.limit = 100;
      const resp = await listProjects(filters);
      setProjects(resp.projects || resp.items || []);
      setTotalProjects(resp.total || 0);
    } catch (e: any) {
      setError(e.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, searchQuery]);

  const loadTemplates = useCallback(async () => {
    try {
      const tpl = await listTemplates();
      setTemplates(tpl);
    } catch {
      // templates may not be available
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadTemplates();
  }, [loadProjects, loadTemplates]);

  const summaryStats = useMemo(() => {
    const active = projects.filter((p) => p.status === 'active').length;
    const planning = projects.filter((p) => p.status === 'planning').length;
    const completed = projects.filter((p) => p.status === 'completed').length;
    const paused = projects.filter((p) => p.status === 'paused').length;
    const totalMilestones = projects.reduce((acc, p) => acc + (p.milestones?.length || 0), 0);
    const completedMilestones = projects.reduce(
      (acc, p) => acc + (p.milestones?.filter((m) => m.status === 'completed').length || 0),
      0
    );
    const overdueMilestones = projects.reduce(
      (acc, p) => acc + (p.milestones?.filter((m) => m.status === 'overdue').length || 0),
      0
    );
    return { active, planning, completed, paused, totalMilestones, completedMilestones, overdueMilestones };
  }, [projects]);

  const allMilestones = useMemo(() => {
    const items: { project: Project; milestone: Milestone }[] = [];
    projects
      .filter((p) => p.status === 'active' || p.status === 'planning')
      .forEach((p) => {
        (p.milestones || []).forEach((m) => {
          items.push({ project: p, milestone: m });
        });
      });
    items.sort((a, b) => {
      if (a.milestone.due_date && b.milestone.due_date) {
        return new Date(a.milestone.due_date).getTime() - new Date(b.milestone.due_date).getTime();
      }
      if (a.milestone.due_date) return -1;
      if (b.milestone.due_date) return 1;
      return new Date(a.milestone.created_at).getTime() - new Date(b.milestone.created_at).getTime();
    });
    return items;
  }, [projects]);

  const handleCreateProject = useCallback(async () => {
    if (!createForm.name.trim()) return;
    try {
      setCreateLoading(true);
      const input: ProjectInput = {
        ...createForm,
        tags: createForm.tags && createForm.tags.length > 0 ? createForm.tags : undefined,
      };
      if (createFromTemplate) {
        input.template_id = createFromTemplate.id;
      }
      await createProject(input);
      setShowCreateModal(false);
      setCreateFromTemplate(null);
      setCreateForm({ name: '', description: '', status: 'planning', priority: 'medium', owner: '', tags: [] });
      await loadProjects();
    } catch (e: any) {
      setError(e.message || 'Failed to create project');
    } finally {
      setCreateLoading(false);
    }
  }, [createForm, createFromTemplate, loadProjects]);

  const handleDeleteProject = useCallback(
    async (id: string) => {
      if (!confirm('Delete this project? This cannot be undone.')) return;
      try {
        await deleteProject(id);
        await loadProjects();
      } catch (e: any) {
        setError(e.message || 'Failed to delete project');
      }
    },
    [loadProjects]
  );

  const handleStartEditMilestone = useCallback((projectId: string, milestone: Milestone) => {
    setEditingMilestone({ projectId, milestone });
    setMilestoneForm({
      title: milestone.title,
      description: milestone.description || '',
      due_date: milestone.due_date || '',
      status: milestone.status,
    });
  }, []);

  const handleSaveMilestone = useCallback(async () => {
    if (!editingMilestone) return;
    try {
      await updateMilestone(editingMilestone.projectId, editingMilestone.milestone.id, milestoneForm);
      setEditingMilestone(null);
      await loadProjects();
    } catch (e: any) {
      setError(e.message || 'Failed to update milestone');
    }
  }, [editingMilestone, milestoneForm, loadProjects]);

  const handleDeleteMilestone = useCallback(
    async (projectId: string, milestoneId: string) => {
      try {
        await deleteMilestone(projectId, milestoneId);
        await loadProjects();
      } catch (e: any) {
        setError(e.message || 'Failed to delete milestone');
      }
    },
    [loadProjects]
  );

  const handleAddMilestone = useCallback(async () => {
    if (!addingMilestoneProjectId || !newMilestoneForm.title.trim()) return;
    try {
      await addMilestone(addingMilestoneProjectId, newMilestoneForm);
      setAddingMilestoneProjectId(null);
      setNewMilestoneForm({ title: '', description: '', due_date: '', status: 'pending' });
      await loadProjects();
    } catch (e: any) {
      setError(e.message || 'Failed to add milestone');
    }
  }, [addingMilestoneProjectId, newMilestoneForm, loadProjects]);

  const openCreateFromTemplate = useCallback((tpl: ProjectTemplate) => {
    setCreateFromTemplate(tpl);
    setCreateForm({
      name: '',
      description: tpl.description || '',
      status: 'planning',
      priority: 'medium',
      owner: '',
      tags: tpl.default_tags || [],
    });
    setShowCreateModal(true);
  }, []);

  const openCreateBlank = useCallback(() => {
    setCreateFromTemplate(null);
    setCreateForm({ name: '', description: '', status: 'planning', priority: 'medium', owner: '', tags: [] });
    setShowCreateModal(true);
  }, []);

  // --- Deliverables ---
  const [deliverables, setDeliverables] = useState<Record<string, Deliverable[]>>({});
  const [deliverablesLoading, setDeliverablesLoading] = useState<string | null>(null);

  const handleDownloadDeliverables = useCallback(async (projectId: string) => {
    setDeliverablesLoading(projectId);
    try {
      const data = await fetchDeliverables(projectId);
      setDeliverables(prev => ({ ...prev, [projectId]: data.files }));
      // Trigger download for each file
      for (const file of data.files) {
        if (file.url) {
          const a = document.createElement('a');
          a.href = file.url;
          a.download = file.filename;
          a.click();
        }
      }
    } catch (e: any) {
      setError(e.message || 'Failed to fetch deliverables');
    }
    setDeliverablesLoading(null);
  }, []);

  // --- Status Controls ---
  const handleStatusChange = useCallback(async (projectId: string, newStatus: Project['status']) => {
    try {
      await updateProject(projectId, { status: newStatus });
      await loadProjects();
    } catch (e: any) {
      setError(e.message || 'Failed to update project status');
    }
  }, [loadProjects]);

  // --- Team View ---
  const [expandedTeam, setExpandedTeam] = useState<string | null>(null);
  const [teamData, setTeamData] = useState<Record<string, TeamMember[]>>({});
  const [teamLoading, setTeamLoading] = useState<string | null>(null);

  const handleToggleTeam = useCallback(async (projectId: string) => {
    if (expandedTeam === projectId) {
      setExpandedTeam(null);
      return;
    }
    setExpandedTeam(projectId);
    if (!teamData[projectId]) {
      setTeamLoading(projectId);
      try {
        const data = await fetchProjectTeam(projectId);
        setTeamData(prev => ({ ...prev, [projectId]: data.members }));
      } catch {
        setTeamData(prev => ({ ...prev, [projectId]: [] }));
      }
      setTeamLoading(null);
    }
  }, [expandedTeam, teamData]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const tabs: { key: TabView; label: string }[] = [
    { key: 'projects', label: 'Projects' },
    { key: 'templates', label: 'Templates' },
    { key: 'timeline', label: 'Timeline' },
  ];

  return (
    <div className="p-6 bg-nc-bg min-h-screen">
      {/* Tab Navigation */}
      <div className="flex items-center gap-2 mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-nc-accent text-white'
                : 'bg-nc-surface text-nc-text-dim hover:bg-nc-surface-2 border border-nc-border'
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={openCreateBlank}
          className="px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          + New Project
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-800 rounded-lg text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-800 hover:opacity-70 font-bold">
            ×
          </button>
        </div>
      )}

      {/* Projects View */}
      {activeTab === 'projects' && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">{totalProjects}</div>
              <div className="text-sm text-nc-text-dim">Total Projects</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-green-800">{summaryStats.active}</div>
              <div className="text-sm text-nc-text-dim">Active</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-blue-800">{summaryStats.planning}</div>
              <div className="text-sm text-nc-text-dim">Planning</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">{summaryStats.completed}</div>
              <div className="text-sm text-nc-text-dim">Completed</div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-6">
            <input
              type="text"
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="px-3 py-2 bg-nc-surface border border-nc-border rounded-lg text-sm text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-nc-surface border border-nc-border rounded-lg text-sm text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
            >
              <option value="">All Statuses</option>
              <option value="planning">Planning</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="px-3 py-2 bg-nc-surface border border-nc-border rounded-lg text-sm text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
            >
              <option value="">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {/* Project Cards Grid */}
          {loading ? (
            <div className="flex items-center justify-center py-20 text-nc-text-dim">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-nc-text-dim mb-2">No projects found</div>
              <button
                onClick={openCreateBlank}
                className="px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium"
              >
                Create your first project
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="bg-nc-surface border border-nc-border rounded-xl p-5 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-nc-text font-semibold text-base truncate flex-1 mr-2">{project.name}</h3>
                    <button
                      onClick={() => handleDeleteProject(project.id)}
                      className="text-nc-text-dim hover:text-red-800 text-sm flex-shrink-0"
                      title="Delete project"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="flex items-center gap-2 mb-3">
                    <Badge {...(STATUS_BADGE[project.status] || STATUS_BADGE.planning)} />
                    <Badge {...(PRIORITY_BADGE[project.priority] || PRIORITY_BADGE.medium)} />
                  </div>
                  {project.description && (
                    <p className="text-nc-text-dim text-sm mb-3 line-clamp-2">{project.description}</p>
                  )}
                  <div className="mb-3">
                    <ProgressBar milestones={project.milestones} />
                  </div>
                  <div className="flex items-center justify-between">
                    <AgentAvatars owner={project.owner} />
                    {project.tags && project.tags.length > 0 && (
                      <div className="flex gap-1 flex-wrap justify-end">
                        {project.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-0.5 bg-nc-surface-2 text-nc-text-dim rounded text-xs"
                          >
                            {tag}
                          </span>
                        ))}
                        {project.tags.length > 3 && (
                          <span className="text-xs text-nc-text-dim">+{project.tags.length - 3}</span>
                        )}
                      </div>
                    )}
                  </div>
                  {/* Milestones section */}
                  {project.milestones && project.milestones.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-nc-border">
                      <div className="text-xs font-medium text-nc-text-dim mb-2">Milestones</div>
                      <div className="space-y-1.5">
                        {project.milestones.map((ms) => (
                          <div key={ms.id} className="flex items-center justify-between text-xs">
                            {editingMilestone &&
                            editingMilestone.projectId === project.id &&
                            editingMilestone.milestone.id === ms.id ? (
                              <div className="flex-1 flex items-center gap-1">
                                <input
                                  type="text"
                                  value={milestoneForm.title}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({ ...f, title: e.target.value }))
                                  }
                                  className="flex-1 px-1.5 py-0.5 bg-nc-surface-2 border border-nc-border rounded text-xs text-nc-text focus:outline-none"
                                />
                                <select
                                  value={milestoneForm.status}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({
                                      ...f,
                                      status: e.target.value as MilestoneInput['status'],
                                    }))
                                  }
                                  className="px-1 py-0.5 bg-nc-surface-2 border border-nc-border rounded text-xs text-nc-text"
                                >
                                  <option value="pending">Pending</option>
                                  <option value="in_progress">In Progress</option>
                                  <option value="completed">Completed</option>
                                  <option value="overdue">Overdue</option>
                                </select>
                                <input
                                  type="date"
                                  value={milestoneForm.due_date || ''}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({ ...f, due_date: e.target.value }))
                                  }
                                  className="px-1 py-0.5 bg-nc-surface-2 border border-nc-border rounded text-xs text-nc-text"
                                />
                                <button
                                  onClick={handleSaveMilestone}
                                  className="text-green-800 hover:opacity-70 font-bold"
                                >
                                  ✓
                                </button>
                                <button
                                  onClick={() => setEditingMilestone(null)}
                                  className="text-nc-text-dim hover:opacity-70"
                                >
                                  ✕
                                </button>
                              </div>
                            ) : (
                              <>
                                <div className="flex items-center gap-1.5 flex-1 min-w-0">
                                  <span
                                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                      ms.status === 'completed'
                                        ? 'bg-green-800'
                                        : ms.status === 'overdue'
                                        ? 'bg-red-800'
                                        : ms.status === 'in_progress'
                                        ? 'bg-yellow-800'
                                        : 'bg-blue-800'
                                    }`}
                                  />
                                  <span className="text-nc-text truncate">{ms.title}</span>
                                </div>
                                <div className="flex items-center gap-1 flex-shrink-0">
                                  {ms.due_date && (
                                    <span className="text-nc-text-dim">{formatDate(ms.due_date)}</span>
                                  )}
                                  <button
                                    onClick={() => handleStartEditMilestone(project.id, ms)}
                                    className="text-nc-text-dim hover:text-nc-accent"
                                    title="Edit milestone"
                                  >
                                    ✎
                                  </button>
                                  <button
                                    onClick={() => handleDeleteMilestone(project.id, ms.id)}
                                    className="text-nc-text-dim hover:text-red-800"
                                    title="Delete milestone"
                                  >
                                    ✕
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Add milestone inline */}
                  {addingMilestoneProjectId === project.id ? (
                    <div className="mt-2 pt-2 border-t border-nc-border space-y-2">
                      <input
                        type="text"
                        placeholder="Milestone title"
                        value={newMilestoneForm.title}
                        onChange={(e) => setNewMilestoneForm((f) => ({ ...f, title: e.target.value }))}
                        className="w-full px-2 py-1 bg-nc-surface-2 border border-nc-border rounded text-xs text-nc-text placeholder:text-nc-text-dim focus:outline-none"
                      />
                      <div className="flex gap-1">
                        <input
                          type="date"
                          value={newMilestoneForm.due_date || ''}
                          onChange={(e) => setNewMilestoneForm((f) => ({ ...f, due_date: e.target.value }))}
                          className="flex-1 px-2 py-1 bg-nc-surface-2 border border-nc-border rounded text-xs text-nc-text"
                        />
                        <button
                          onClick={handleAddMilestone}
                          className="px-2 py-1 bg-nc-accent text-white rounded text-xs font-medium"
                        >
                          Add
                        </button>
                        <button
                          onClick={() => {
                            setAddingMilestoneProjectId(null);
                            setNewMilestoneForm({ title: '', description: '', due_date: '', status: 'pending' });
                          }}
                          className="px-2 py-1 bg-nc-surface-2 text-nc-text-dim rounded text-xs"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setAddingMilestoneProjectId(project.id)}
                      className="mt-2 text-xs text-nc-accent hover:opacity-70"
                    >
                      + Add Milestone
                    </button>
                  )}
                  <div className="mt-2 text-xs text-nc-text-dim">
                    Updated {formatDate(project.updated_at)}
                  </div>

                  {/* Status Controls + Deliverables + Team */}
                  <div className="mt-3 pt-3 border-t border-nc-border space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      {project.status === 'active' && (
                        <button onClick={() => handleStatusChange(project.id, 'paused')}
                          className="px-2.5 py-1 text-xs font-medium bg-nc-yellow/10 text-yellow-700 border border-nc-yellow/20 rounded-lg hover:bg-nc-yellow/20 transition-colors">
                          Pause
                        </button>
                      )}
                      {project.status === 'paused' && (
                        <button onClick={() => handleStatusChange(project.id, 'active')}
                          className="px-2.5 py-1 text-xs font-medium bg-nc-green/10 text-nc-green border border-nc-green/20 rounded-lg hover:bg-nc-green/20 transition-colors">
                          Resume
                        </button>
                      )}
                      {(project.status === 'active' || project.status === 'paused') && (
                        <button onClick={() => handleStatusChange(project.id, 'archived')}
                          className="px-2.5 py-1 text-xs font-medium bg-nc-red/10 text-nc-red border border-nc-red/20 rounded-lg hover:bg-nc-red/20 transition-colors">
                          Cancel
                        </button>
                      )}
                      <button onClick={() => handleDownloadDeliverables(project.id)}
                        disabled={deliverablesLoading === project.id}
                        className="px-2.5 py-1 text-xs font-medium bg-nc-accent/10 text-nc-accent border border-nc-accent/20 rounded-lg hover:bg-nc-accent/20 transition-colors disabled:opacity-50">
                        {deliverablesLoading === project.id ? 'Loading...' : 'Download Deliverables'}
                      </button>
                      <button onClick={() => handleToggleTeam(project.id)}
                        className="px-2.5 py-1 text-xs font-medium bg-nc-surface-2 text-nc-text-dim border border-nc-border rounded-lg hover:text-nc-text transition-colors">
                        {expandedTeam === project.id ? 'Hide Team' : 'View Team'}
                      </button>
                    </div>

                    {/* Deliverables list */}
                    {deliverables[project.id] && deliverables[project.id].length > 0 && (
                      <div className="text-xs text-nc-text-dim">
                        {deliverables[project.id].length} deliverable{deliverables[project.id].length !== 1 ? 's' : ''} available
                      </div>
                    )}

                    {/* Team expansion */}
                    {expandedTeam === project.id && (
                      <div className="pt-2">
                        {teamLoading === project.id ? (
                          <span className="text-xs text-nc-text-dim">Loading team...</span>
                        ) : teamData[project.id] && teamData[project.id].length > 0 ? (
                          <div className="space-y-1.5">
                            {teamData[project.id].map((member) => (
                              <div key={member.agent_id} className="flex items-center gap-2 text-xs">
                                <div className="w-6 h-6 rounded-full bg-nc-accent/20 text-nc-accent flex items-center justify-center text-[10px] font-semibold">
                                  {member.agent_name.charAt(0)}
                                </div>
                                <span className="text-nc-text font-medium">{member.agent_name}</span>
                                <span className="text-nc-text-dim">{member.role}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-nc-text-dim">No team members assigned</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Templates View */}
      {activeTab === 'templates' && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">{templates.length}</div>
              <div className="text-sm text-nc-text-dim">Templates Available</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">
                {new Set(templates.map((t) => t.category).filter(Boolean)).size}
              </div>
              <div className="text-sm text-nc-text-dim">Categories</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">
                {templates.reduce((a, t) => a + (t.default_milestones?.length || 0), 0)}
              </div>
              <div className="text-sm text-nc-text-dim">Default Milestones</div>
            </div>
          </div>

          {templates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-nc-text-dim mb-2">No templates available</div>
              <p className="text-sm text-nc-text-dim">Templates will appear here once configured.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {templates.map((tpl) => (
                <div
                  key={tpl.id}
                  className="bg-nc-surface border border-nc-border rounded-xl p-5 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-nc-text font-semibold text-base">{tpl.name}</h3>
                    {tpl.category && (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                        {tpl.category}
                      </span>
                    )}
                  </div>
                  {tpl.description && (
                    <p className="text-nc-text-dim text-sm mb-3 line-clamp-3">{tpl.description}</p>
                  )}
                  {tpl.default_milestones && tpl.default_milestones.length > 0 && (
                    <div className="mb-3">
                      <div className="text-xs font-medium text-nc-text-dim mb-1">
                        {tpl.default_milestones.length} milestone{tpl.default_milestones.length !== 1 ? 's' : ''}
                      </div>
                      <div className="space-y-1">
                        {tpl.default_milestones.slice(0, 4).map((ms, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-xs text-nc-text">
                            <span className="w-1.5 h-1.5 bg-nc-accent rounded-full" />
                            {ms.title}
                          </div>
                        ))}
                        {tpl.default_milestones.length > 4 && (
                          <div className="text-xs text-nc-text-dim">
                            +{tpl.default_milestones.length - 4} more
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {tpl.default_tags && tpl.default_tags.length > 0 && (
                    <div className="flex gap-1 flex-wrap mb-3">
                      {tpl.default_tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 bg-nc-surface-2 text-nc-text-dim rounded text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => openCreateFromTemplate(tpl)}
                    className="w-full mt-2 px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
                  >
                    Create from Template
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Timeline View */}
      {activeTab === 'timeline' && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-nc-text">{summaryStats.totalMilestones}</div>
              <div className="text-sm text-nc-text-dim">Total Milestones</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-green-800">{summaryStats.completedMilestones}</div>
              <div className="text-sm text-nc-text-dim">Completed</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-red-800">{summaryStats.overdueMilestones}</div>
              <div className="text-sm text-nc-text-dim">Overdue</div>
            </div>
            <div className="bg-nc-surface border border-nc-border rounded-xl p-4">
              <div className="text-2xl font-bold text-blue-800">
                {summaryStats.totalMilestones - summaryStats.completedMilestones - summaryStats.overdueMilestones}
              </div>
              <div className="text-sm text-nc-text-dim">Remaining</div>
            </div>
          </div>

          {allMilestones.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-nc-text-dim">No milestones across active projects</div>
            </div>
          ) : (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-nc-border" />
              <div className="space-y-4">
                {allMilestones.map(({ project, milestone }, idx) => {
                  const msStatus = MILESTONE_STATUS_BADGE[milestone.status] || MILESTONE_STATUS_BADGE.pending;
                  return (
                    <div key={`${project.id}-${milestone.id}`} className="relative flex items-start gap-4 pl-12">
                      {/* Dot */}
                      <div
                        className={`absolute left-4 top-3 w-4 h-4 rounded-full border-2 border-nc-surface ${
                          milestone.status === 'completed'
                            ? 'bg-green-800'
                            : milestone.status === 'overdue'
                            ? 'bg-red-800'
                            : milestone.status === 'in_progress'
                            ? 'bg-yellow-800'
                            : 'bg-blue-800'
                        }`}
                      />
                      <div className="flex-1 bg-nc-surface border border-nc-border rounded-xl p-4 hover:shadow-sm transition-shadow">
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex-1 min-w-0">
                            {editingMilestone &&
                            editingMilestone.projectId === project.id &&
                            editingMilestone.milestone.id === milestone.id ? (
                              <div className="flex items-center gap-2 flex-wrap">
                                <input
                                  type="text"
                                  value={milestoneForm.title}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({ ...f, title: e.target.value }))
                                  }
                                  className="px-2 py-1 bg-nc-surface-2 border border-nc-border rounded text-sm text-nc-text focus:outline-none flex-1 min-w-0"
                                />
                                <select
                                  value={milestoneForm.status}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({
                                      ...f,
                                      status: e.target.value as MilestoneInput['status'],
                                    }))
                                  }
                                  className="px-2 py-1 bg-nc-surface-2 border border-nc-border rounded text-sm text-nc-text"
                                >
                                  <option value="pending">Pending</option>
                                  <option value="in_progress">In Progress</option>
                                  <option value="completed">Completed</option>
                                  <option value="overdue">Overdue</option>
                                </select>
                                <input
                                  type="date"
                                  value={milestoneForm.due_date || ''}
                                  onChange={(e) =>
                                    setMilestoneForm((f) => ({ ...f, due_date: e.target.value }))
                                  }
                                  className="px-2 py-1 bg-nc-surface-2 border border-nc-border rounded text-sm text-nc-text"
                                />
                                <button
                                  onClick={handleSaveMilestone}
                                  className="px-3 py-1 bg-nc-accent text-white rounded text-sm font-medium"
                                >
                                  Save
                                </button>
                                <button
                                  onClick={() => setEditingMilestone(null)}
                                  className="px-3 py-1 bg-nc-surface-2 text-nc-text-dim rounded text-sm"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <>
                                <h4 className="text-nc-text font-medium text-sm">{milestone.title}</h4>
                                {milestone.description && (
                                  <p className="text-nc-text-dim text-xs mt-0.5">{milestone.description}</p>
                                )}
                              </>
                            )}
                          </div>
                          {!(
                            editingMilestone &&
                            editingMilestone.projectId === project.id &&
                            editingMilestone.milestone.id === milestone.id
                          ) && (
                            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                              <Badge {...msStatus} />
                              <button
                                onClick={() => handleStartEditMilestone(project.id, milestone)}
                                className="text-nc-text-dim hover:text-nc-accent text-sm"
                                title="Edit"
                              >
                                ✎
                              </button>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-2 text-xs text-nc-text-dim">
                          <span className="px-2 py-0.5 bg-nc-surface-2 rounded">{project.name}</span>
                          {milestone.due_date && <span>Due: {formatDate(milestone.due_date)}</span>}
                          {project.owner && <span>Owner: {project.owner}</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-nc-surface rounded-2xl border border-nc-border shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-nc-text">
                  {createFromTemplate ? `New from "${createFromTemplate.name}"` : 'New Project'}
                </h2>
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateFromTemplate(null);
                  }}
                  className="text-nc-text-dim hover:text-nc-text text-xl"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Project Name *</label>
                  <input
                    type="text"
                    value={createForm.name}
                    onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Enter project name"
                    className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Description</label>
                  <textarea
                    value={createForm.description || ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Project description"
                    rows={3}
                    className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent resize-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-nc-text mb-1">Status</label>
                    <select
                      value={createForm.status || 'planning'}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          status: e.target.value as ProjectInput['status'],
                        }))
                      }
                      className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                    >
                      <option value="planning">Planning</option>
                      <option value="active">Active</option>
                      <option value="paused">Paused</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-nc-text mb-1">Priority</label>
                    <select
                      value={createForm.priority || 'medium'}
                      onChange={(e) =>
                        setCreateForm((f) => ({
                          ...f,
                          priority: e.target.value as ProjectInput['priority'],
                        }))
                      }
                      className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text focus:outline-none focus:ring-2 focus:ring-nc-accent"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Owner</label>
                  <input
                    type="text"
                    value={createForm.owner || ''}
                    onChange={(e) => setCreateForm((f) => ({ ...f, owner: e.target.value }))}
                    placeholder="Project owner"
                    className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-nc-text mb-1">Tags (comma separated)</label>
                  <input
                    type="text"
                    value={(createForm.tags || []).join(', ')}
                    onChange={(e) =>
                      setCreateForm((f) => ({
                        ...f,
                        tags: e.target.value
                          .split(',')
                          .map((t) => t.trim())
                          .filter(Boolean),
                      }))
                    }
                    placeholder="tag1, tag2, tag3"
                    className="w-full px-3 py-2 bg-nc-surface-2 border border-nc-border rounded-lg text-sm text-nc-text placeholder:text-nc-text-dim focus:outline-none focus:ring-2 focus:ring-nc-accent"
                  />
                </div>

                {createFromTemplate && createFromTemplate.default_milestones && (
                  <div className="p-3 bg-nc-surface-2 rounded-lg border border-nc-border">
                    <div className="text-xs font-medium text-nc-text-dim mb-2">
                      Template includes {createFromTemplate.default_milestones.length} milestone
                      {createFromTemplate.default_milestones.length !== 1 ? 's' : ''}:
                    </div>
                    <div className="space-y-1">
                      {createFromTemplate.default_milestones.map((ms, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs text-nc-text">
                          <span className="w-1.5 h-1.5 bg-nc-accent rounded-full" />
                          {ms.title}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-nc-border">
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setCreateFromTemplate(null);
                  }}
                  className="px-4 py-2 bg-nc-surface-2 text-nc-text-dim rounded-lg text-sm font-medium hover:bg-nc-border transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateProject}
                  disabled={createLoading || !createForm.name.trim()}
                  className="px-4 py-2 bg-nc-accent text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createLoading ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}