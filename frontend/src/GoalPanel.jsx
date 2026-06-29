import React, { useEffect, useState } from 'react';
import { readItems, writeItems } from './goalStorage';
import { freshTasks, markTask, runExecutionPipeline } from './executionEngine';
import { useProject } from './projectContext.jsx';

const WORKSPACE_KEY = 'codem8s-workspace-v1';

function readWorkspace() {
  try { return JSON.parse(localStorage.getItem(WORKSPACE_KEY) || '[]'); }
  catch { return []; }
}

function latestWorkspaceProjectId() {
  return readWorkspace()?.[0]?.project_id || '';
}

function normalizeTasks(tasks = []) {
  const oldRepair = tasks.find((task) => task.name === 'Repair pass');
  const byName = Object.fromEntries(tasks.map((task) => [task.name, task]));
  return freshTasks().map((task) => {
    const existing = byName[task.name] || (task.name === 'Repair' ? oldRepair : null);
    return existing ? { ...task, ...existing, name: task.name } : task;
  });
}

export default function GoalPanel(props = {}) {
  const shared = useProject();
  const project = props.project || shared.project;
  const setProject = props.setProject || shared.setProject;
  const setSandbox = props.setSandbox || shared.setSandbox;
  const refreshSandbox = props.refreshSandbox || shared.refreshSandbox;
  const refreshSnapshots = props.refreshSnapshots || shared.refreshSnapshots;
  const setNotice = props.setNotice || shared.setNotice;
  const post = props.post || shared.post;
  const createSharedProject = props.createProject || shared.createProject;
  const buildAllIncremental = props.buildAllIncremental || shared.buildAllIncremental;

  const [items, setItems] = useState(() => readItems().map((item) => ({ ...item, tasks: normalizeTasks(item.tasks) })));
  const [text, setText] = useState('Build this project and get it running.');
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState('');
  const [lastPreview, setLastPreview] = useState(null);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    writeItems(items);
  }, [items]);

  function addChat(role, body) {
    props.addChat?.(role, body);
    window.dispatchEvent(new CustomEvent('codem8s-chat-event', { detail: { role, text: body } }));
  }

  async function createProjectFromGoal(goalTitle) {
    setMessage('Creating project plan');
    return createSharedProject(goalTitle);
  }

  async function getCurrentProject() {
    if (project?.project_id) return project;
    const recentId = latestWorkspaceProjectId();
    if (recentId) {
      setMessage('Opening latest workspace project');
      return shared.openProject(recentId);
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
    const currentId = project?.project_id || latestWorkspaceProjectId();
    setItems((old) => [{ id: String(Date.now()), title, status: 'ready', projectId: currentId, tasks: freshTasks(), history: [] }, ...old].slice(0, 20));
    addChat('system', `Goal created: ${title}`);
  }

  async function runItem(item) {
    setRunning(true);
    setMessage('Execution engine started');
    setNotice?.('Execution engine started');
    setEvents([]);
    updateItem(item.id, { status: 'running', tasks: normalizeTasks(item.tasks), updatedAt: new Date().toISOString() });
    addChat('goal', item.title);
    try {
      const startProject = await getCurrentProject();
      const result = await runExecutionPipeline({
        goal: item,
        project: startProject,
        createProject: createProjectFromGoal,
        post,
        buildAllIncremental,
        onProject: (nextProject) => {
          setProject(nextProject);
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
      addChat('codem8s', result.ok ? `Goal complete: ${item.title}` : `Goal blocked: ${item.title}`);
    } catch (err) {
      updateItem(item.id, { status: 'blocked', updatedAt: new Date().toISOString() });
      setMessage(`Execution blocked: ${String(err.message || err)}`);
      addChat('codem8s', `Execution blocked: ${String(err.message || err)}`);
    } finally {
      setRunning(false);
    }
  }

  function removeItem(id) {
    setItems((old) => old.filter((item) => item.id !== id));
  }

  return (
    <section className="card goal-card">
      <h2>Execution Engine</h2>
      <p>Goals now run through the shared project context and reusable Plan → Checkpoint → Build → Preview → Repair → Validate pipeline.</p>
      {message && <p><b>{message}</b></p>}
      {project && <p><b>Using project:</b> {project.spec?.app_name || project.project_id} · {project.status}</p>}
      {!project && latestWorkspaceProjectId() && <p><b>Ready to use latest workspace project.</b></p>}
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
