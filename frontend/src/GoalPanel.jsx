import React, { useEffect, useState } from 'react';
import { readItems, writeItems } from './goalStorage';
import { freshTasks, markTask, runExecutionPipeline } from './executionEngine';

const API = import.meta.env.VITE_API_BASE_URL || 'https://codem8s-docker.onrender.com';
const WORKSPACE_KEY = 'codem8s-workspace-v1';

function latestWorkspaceProjectId() {
  try {
    const items = JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '[]');
    return items?.[0]?.project_id || '';
  } catch {
    return '';
  }
}

function normalizeTasks(tasks = []) {
  const oldRepair = tasks.find((task) => task.name === 'Repair pass');
  const byName = Object.fromEntries(tasks.map((task) => [task.name, task]));
  return freshTasks().map((task) => {
    const existing = byName[task.name] || (task.name === 'Repair' ? oldRepair : null);
    return existing ? { ...task, ...existing, name: task.name } : task;
  });
}

export default function GoalPanel({ project, setProject, setSandbox, refreshSandbox, refreshSnapshots, addChat, setNotice }) {
  const [items, setItems] = useState(() => readItems().map((item) => ({ ...item, tasks: normalizeTasks(item.tasks) })));
  const [text, setText] = useState('Build this project and get it running.');
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState('');
  const [lastPreview, setLastPreview] = useState(null);
  const [externalProject, setExternalProject] = useState(null);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    writeItems(items);
  }, [items]);

  async function request(path, options = {}) {
    const res = await fetch(API + path, options);
    const body = await res.text();
    let data = null;
    try { data = body ? JSON.parse(body) : null; } catch {}
    if (!res.ok) throw new Error(data?.detail || body || `Request failed ${res.status}`);
    return data;
  }

  function post(path, body) {
    return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  }

  async function createProjectFromGoal(goalTitle) {
    setMessage('Creating project plan');
    const created = await post('/projects', { idea: goalTitle, use_ai: true });
    setExternalProject(created);
    setProject?.(created);
    return created;
  }

  async function getCurrentProject() {
    if (project?.project_id) return project;
    if (externalProject?.project_id) return externalProject;
    const recentId = latestWorkspaceProjectId();
    if (recentId) {
      setMessage('Opening latest workspace project');
      const loaded = await post(`/projects/${recentId}/validate`, {});
      setExternalProject(loaded);
      setProject?.(loaded);
      return loaded;
    }
    return null;
  }

  function updateItem(id, updater) {
    setItems((old) => old.map((item) => item.id === id ? (typeof updater === 'function' ? updater(item) : { ...item, ...updater }) : item));
  }

  function updateTask(id, name, status, note = '') {
    updateItem(id, (item) => ({ ...item, tasks: markTask(normalizeTasks(item.tasks), name, status, note) }));
  }

  function addItem() {
    const title = text.trim();
    if (!title) return;
    const currentId = project?.project_id || externalProject?.project_id || latestWorkspaceProjectId();
    setItems((old) => [{ id: String(Date.now()), title, status: 'ready', projectId: currentId, tasks: freshTasks(), history: [] }, ...old].slice(0, 20));
    addChat?.('system', `Goal created: ${title}`);
  }

  async function runItem(item) {
    setRunning(true);
    setMessage('Execution engine started');
    setNotice?.('Execution engine started');
    setEvents([]);
    updateItem(item.id, { status: 'running', tasks: normalizeTasks(item.tasks), updatedAt: new Date().toISOString() });
    addChat?.('goal', item.title);
    try {
      const startProject = await getCurrentProject();
      const result = await runExecutionPipeline({
        goal: item,
        project: startProject,
        createProject: createProjectFromGoal,
        post,
        onProject: (nextProject) => {
          setExternalProject(nextProject);
          setProject?.(nextProject);
          updateItem(item.id, { projectId: nextProject.project_id });
        },
        onSandbox: async (sandbox) => {
          setSandbox?.(sandbox);
          setLastPreview(sandbox);
          if (sandbox?.project_id) await refreshSandbox?.(sandbox.project_id);
        },
        onMessage: (msg) => {
          setMessage(msg);
          setNotice?.(msg);
        },
        onTask: (name, status, note) => updateTask(item.id, name, status, note),
        onEvent: (event) => {
          setEvents((old) => [event, ...old].slice(0, 20));
          updateItem(item.id, (goal) => ({ ...goal, history: [event, ...(goal.history || [])].slice(0, 30) }));
        },
        maxRepairRounds: 6,
      });
      if (result.project?.project_id) await refreshSnapshots?.(result.project.project_id);
      updateItem(item.id, { status: result.ok ? 'done' : 'blocked', updatedAt: new Date().toISOString() });
      addChat?.('codem8s', result.ok ? `Goal complete: ${item.title}` : `Goal blocked: ${item.title}`);
    } catch (err) {
      updateItem(item.id, { status: 'blocked', updatedAt: new Date().toISOString() });
      setMessage(`Execution blocked: ${String(err.message || err)}`);
      addChat?.('codem8s', `Execution blocked: ${String(err.message || err)}`);
    } finally {
      setRunning(false);
    }
  }

  function removeItem(id) {
    setItems((old) => old.filter((item) => item.id !== id));
  }

  const shownProject = project || externalProject;

  return (
    <section className="card goal-card">
      <h2>Execution Engine</h2>
      <p>Goals now run through a reusable Plan → Checkpoint → Build → Preview → Repair → Validate pipeline.</p>
      {message && <p><b>{message}</b></p>}
      {shownProject && <p><b>Using project:</b> {shownProject.spec?.app_name || shownProject.project_id} · {shownProject.status}</p>}
      {!shownProject && latestWorkspaceProjectId() && <p><b>Ready to use latest workspace project.</b></p>}
      {lastPreview && <p><b>Last preview:</b> {lastPreview.build_ok ? 'green' : 'not green'} {lastPreview.preview_url || ''}</p>}
      {lastPreview?.last_error && <pre className="log bad-box">{lastPreview.last_error}</pre>}
      <textarea value={text} onChange={(event) => setText(event.target.value)} />
      <button onClick={addItem} disabled={running}>Create Goal</button>
      <div className="goal-list">
        {items.length === 0 ? <p>No goals yet.</p> : items.map((item) => (
          <article className={`goal-item ${item.status}`} key={item.id}>
            <div className="row">
              <b>{item.title}</b>
              <span className="pill">{item.status}</span>
              <button onClick={() => runItem(item)} disabled={running}>Run / Continue</button>
              <button className="warning" onClick={() => removeItem(item.id)} disabled={running}>Delete</button>
            </div>
            {normalizeTasks(item.tasks).map((task) => <div className={`goal-step ${task.status}`} key={task.name}>{task.status === 'done' ? '☑' : task.status === 'running' ? '…' : task.status === 'blocked' ? '⚠' : '☐'} {task.name} {task.note ? <small>{task.note}</small> : null}</div>)}
          </article>
        ))}
      </div>
      {events.length > 0 && <div className="timeline-list">{events.map((event) => <div className="timeline-item" key={`${event.at}-${event.message}`}><b>{event.message}</b><span>{event.at}</span></div>)}</div>}
    </section>
  );
}
