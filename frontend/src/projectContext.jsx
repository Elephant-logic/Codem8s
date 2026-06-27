import React, { createContext, useContext, useMemo, useState } from 'react';

export const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
export const WORKSPACE_KEY = 'codem8s-workspace-v1';

const ProjectContext = createContext(null);

function readWorkspace() {
  try {
    return JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '[]');
  } catch {
    return [];
  }
}

function writeWorkspaceProject(project) {
  if (!project?.project_id) return;
  const item = {
    project_id: project.project_id,
    name: project.spec?.app_name || 'Untitled project',
    stack: project.spec?.stack || '',
    status: project.status || 'working',
    files: Object.keys(project.files || {}).length,
    updated_at: new Date().toISOString(),
  };
  const next = [item, ...readWorkspace().filter((entry) => entry.project_id !== item.project_id)].slice(0, 20);
  localStorage.setItem(WORKSPACE_KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent('codem8s-workspace-updated', { detail: item }));
}

export function ProjectProvider({ children }) {
  const [project, rawSetProject] = useState(null);
  const [sandbox, setSandbox] = useState(null);
  const [logs, setLogs] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [notice, setNotice] = useState('');

  async function request(path, options = {}) {
    const res = await fetch(API + path, options);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch {}
    if (!res.ok) throw new Error(data?.detail || text || `Request failed ${res.status}`);
    return data;
  }

  function post(path, body) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  }

  function setProject(nextProject) {
    rawSetProject(nextProject);
    writeWorkspaceProject(nextProject);
  }

  async function refreshSnapshots(id = project?.project_id) {
    if (!id) return [];
    try {
      const data = await request(`/projects/${id}/snapshots`);
      setSnapshots(data.snapshots || []);
      return data.snapshots || [];
    } catch {
      setSnapshots([]);
      return [];
    }
  }

  async function refreshSandbox(id = project?.project_id) {
    if (!id) return null;
    const latest = await request(`/projects/${id}/sandbox/logs?limit=300`);
    setLogs(latest.logs || []);
    const status = await request(`/projects/${id}/sandbox/status`);
    setSandbox(status);
    return status;
  }

  async function runSandbox(id = project?.project_id) {
    if (!id) return null;
    const result = await post(`/projects/${id}/sandbox/start`, {});
    setSandbox(result);
    await refreshSandbox(id);
    await refreshSnapshots(id);
    return result;
  }

  async function validate(id = project?.project_id) {
    if (!id) return null;
    const validated = await post(`/projects/${id}/validate`, {});
    setProject(validated);
    await refreshSnapshots(validated.project_id);
    return validated;
  }

  async function buildAll(id = project?.project_id) {
    if (!id) return null;
    const built = await post(`/projects/${id}/build-all`, {});
    setProject(built);
    await refreshSnapshots(built.project_id);
    return built;
  }

  async function openProject(id) {
    if (!id) return null;
    const loaded = await post(`/projects/${id}/validate`, {});
    setProject(loaded);
    await refreshSnapshots(id);
    return loaded;
  }

  async function createProject(idea) {
    const created = await post('/projects', { idea, use_ai: true });
    setProject(created);
    await refreshSnapshots(created.project_id);
    return created;
  }

  async function snapshot(label = 'manual checkpoint') {
    if (!project?.project_id) return null;
    const result = await post(`/projects/${project.project_id}/snapshot`, { label });
    await refreshSnapshots(project.project_id);
    return result;
  }

  async function restoreSnapshot(snapshotId) {
    if (!project?.project_id || !snapshotId) return null;
    const restored = await post(`/projects/${project.project_id}/restore/${snapshotId}`, {});
    setProject(restored);
    await refreshSnapshots(restored.project_id);
    return restored;
  }

  const value = useMemo(() => ({
    API,
    project,
    setProject,
    sandbox,
    setSandbox,
    logs,
    setLogs,
    snapshots,
    setSnapshots,
    notice,
    setNotice,
    request,
    post,
    refreshSnapshots,
    refreshSandbox,
    runSandbox,
    validate,
    buildAll,
    openProject,
    createProject,
    snapshot,
    restoreSnapshot,
  }), [project, sandbox, logs, snapshots, notice]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const value = useContext(ProjectContext);
  if (!value) throw new Error('useProject must be used inside ProjectProvider');
  return value;
}
